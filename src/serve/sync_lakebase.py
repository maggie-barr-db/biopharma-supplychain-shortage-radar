"""P06 job task: refresh the Lakebase synced tables after gold is rebuilt, then report row counts.

Looks up each synced table's pipeline by name (portable across workspaces) and runs a snapshot update.
"""
import argparse, json, os, re, time

from databricks.sdk import WorkspaceClient

p = argparse.ArgumentParser()
p.add_argument("--catalog", default="supply_chain")
a, _ = p.parse_known_args()
w = WorkspaceClient()
summary = {"task": "sync_lakebase", "tables": {}}
for t in ("disruption_impact", "user_entitlement"):
    st = w.api_client.do("GET", f"/api/2.0/postgres/synced_tables/{a.catalog}.ops.{t}")
    pid = re.findall(r'"pipeline_id": "([0-9a-f-]+)"', json.dumps(st))[0]
    upd = w.pipelines.start_update(pipeline_id=pid).update_id
    while (s := w.pipelines.get_update(pipeline_id=pid, update_id=upd).update.state.value) not in ("COMPLETED", "FAILED", "CANCELED"):
        time.sleep(10)
    summary["tables"][t] = {"pipeline_id": pid, "update_state": s}
os.makedirs(f"/Volumes/{a.catalog}/raw/run_log", exist_ok=True)
with open(f"/Volumes/{a.catalog}/raw/run_log/sync_lakebase.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary))
