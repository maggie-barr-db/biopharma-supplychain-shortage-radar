"""Run a SQL file statement by statement on the bundle's SQL warehouse, substituting ${name} variables.

Usage: python tools/run_sql.py <file.sql> --profile <p> --warehouse <id> [--var name=value ...]
Prints one JSON line per statement (state, first line) so the output can be committed as evidence.
"""
import argparse, json, re, subprocess

p = argparse.ArgumentParser()
p.add_argument("file")
p.add_argument("--profile", required=True)
p.add_argument("--warehouse", required=True)
p.add_argument("--var", action="append", default=[])
a = p.parse_args()
sql = open(a.file).read()
for kv in a.var:
    k, v = kv.split("=", 1)
    sql = sql.replace("${" + k + "}", v)
sql = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
for stmt in [s.strip() for s in re.split(r";\s*\n", sql) if s.strip()]:
    body = json.dumps({"warehouse_id": a.warehouse, "statement": stmt, "wait_timeout": "50s"})
    out = subprocess.run(["databricks", "api", "post", "/api/2.0/sql/statements", "--profile", a.profile, "--json", body],
                         capture_output=True, text=True).stdout
    st = json.loads(out)["status"]
    print(json.dumps({"state": st["state"], "statement": stmt.splitlines()[0][:90],
                      "error": st.get("error", {}).get("message", "")[:300] or None}))
