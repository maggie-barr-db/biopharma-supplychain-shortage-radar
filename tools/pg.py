"""Open a Lakebase Postgres connection as the CLI user with a short-lived OAuth token (never printed).

Usage: python tools/pg.py --profile <p> [--file setup.sql] [--sql "SELECT ..."] [--as-user <principal>]
--as-user sets app.user for the session, the same way the app does for the signed-in user.
"""
import argparse, json, subprocess, sys
import psycopg

ENDPOINT = "projects/shortage-radar/branches/production/endpoints/primary"


def connect(profile):
    cred = json.loads(subprocess.run(["databricks", "postgres", "generate-database-credential", ENDPOINT,
                                      "--profile", profile, "-o", "json"], capture_output=True, text=True, check=True).stdout)
    ep = json.loads(subprocess.run(["databricks", "postgres", "get-endpoint", ENDPOINT, "--profile", profile, "-o", "json"],
                                   capture_output=True, text=True, check=True).stdout)
    user = json.loads(subprocess.run(["databricks", "current-user", "me", "--profile", profile, "-o", "json"],
                                     capture_output=True, text=True, check=True).stdout)["userName"]
    return psycopg.connect(host=ep["status"]["hosts"]["host"], dbname="databricks_postgres", user=user,
                           password=cred["token"], sslmode="require", autocommit=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True)
    p.add_argument("--file")
    p.add_argument("--sql", action="append", default=[])
    p.add_argument("--as-user")
    a = p.parse_args()
    with connect(a.profile) as conn, conn.cursor() as cur:
        if a.as_user:
            cur.execute("SELECT set_config('app.user', %s, false)", (a.as_user,))
        if a.file:
            cur.execute(open(a.file).read())
            print(json.dumps({"file": a.file, "status": "applied"}))
        for q in a.sql:
            try:
                cur.execute(q)
                rows = cur.fetchall() if cur.description else []
                cols = [d.name for d in cur.description] if cur.description else []
                print(json.dumps({"sql": q, "columns": cols, "rows": rows[:25], "rowcount": cur.rowcount}, default=str))
            except psycopg.Error as e:
                print(json.dumps({"sql": q, "error": str(e).splitlines()[0]}))
