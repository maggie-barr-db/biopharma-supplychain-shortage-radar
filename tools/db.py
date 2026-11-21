"""Run SQL against the workspace: UC SQL files on the warehouse, or Postgres (Lakebase) as the CLI user.

  python tools/db.py sql <file.sql> --profile <p> --warehouse <id> [--var k=v ...]   # UC, statement by statement
  python tools/db.py pg  --profile <p> [--file f.sql] [--sql "..."] [--as-user <principal>] [--var k=v ...]
${k} placeholders are substituted from --var. Lakebase uses a short-lived OAuth token that is never printed;
--as-user sets app.user the same way the app does for the signed-in user.
"""
import argparse, json, re, subprocess

import psycopg

ENDPOINT = "projects/shortage-radar/branches/production/endpoints/primary"


def _cli(args, profile):
    return json.loads(subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"],
                                     capture_output=True, text=True, check=True).stdout)


def _subst(text, pairs):
    for kv in pairs:
        k, v = kv.split("=", 1)
        text = text.replace("${" + k + "}", v)
    return text


def connect(profile):
    """Lakebase connection as the profile's identity (user or service principal)."""
    cred = _cli(["postgres", "generate-database-credential", ENDPOINT], profile)
    host = _cli(["postgres", "get-endpoint", ENDPOINT], profile)["status"]["hosts"]["host"]
    user = _cli(["current-user", "me"], profile)["userName"]
    return psycopg.connect(host=host, dbname="databricks_postgres", user=user, password=cred["token"],
                           sslmode="require", autocommit=True)


def run_uc(a):
    sql = _subst(open(a.file).read(), a.var)
    sql = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    for stmt in [s.strip() for s in re.split(r";\s*\n", sql) if s.strip()]:
        body = json.dumps({"warehouse_id": a.warehouse, "statement": stmt, "wait_timeout": "50s"})
        st = _cli(["api", "post", "/api/2.0/sql/statements", "--json", body], a.profile)["status"]
        print(json.dumps({"state": st["state"], "statement": stmt.splitlines()[0][:90],
                          "error": st.get("error", {}).get("message", "")[:300] or None}))


def run_pg(a):
    with connect(a.profile) as conn, conn.cursor() as cur:
        if a.as_user:
            cur.execute("SELECT set_config('app.user', %s, false)", (a.as_user,))
        if a.file:
            cur.execute(_subst(open(a.file).read(), a.var))
            print(json.dumps({"file": a.file, "status": "applied"}))
        for q in a.sql:
            try:
                cur.execute(q)
                rows = cur.fetchall() if cur.description else []
                print(json.dumps({"sql": q, "rows": rows[:25], "rowcount": cur.rowcount}, default=str))
            except psycopg.Error as e:
                print(json.dumps({"sql": q, "error": str(e).splitlines()[0]}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["sql", "pg"])
    p.add_argument("file", nargs="?")
    p.add_argument("--profile", required=True)
    p.add_argument("--warehouse")
    p.add_argument("--var", action="append", default=[])
    p.add_argument("--sql", action="append", default=[])
    p.add_argument("--as-user")
    p.add_argument("--file", dest="file_opt")
    a = p.parse_args()
    a.file = a.file or a.file_opt
    run_uc(a) if a.mode == "sql" else run_pg(a)
