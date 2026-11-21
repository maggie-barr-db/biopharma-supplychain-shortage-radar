"""P06 job task: land the Lakebase mitigation workflow back into governed Delta tables.

decisions.mitigation_action -> gold.mitigation_decision (MERGE on action_id, latest state)
decisions.audit_log         -> gold.mitigation_audit    (append new audit rows only)
Both carry the same region row filter as the rest of gold; estimated revenue protected is masked.
Idempotent: rerunning merges the same rows. The Lakebase change data feed (Beta) is the native path;
this task keeps the build working while that feed is in preview.
"""
import argparse, json, os

import pandas as pd
import psycopg
from databricks.sdk import WorkspaceClient
from pyspark.sql import SparkSession

p = argparse.ArgumentParser()
p.add_argument("--catalog", default="supply_chain")
p.add_argument("--endpoint", default="projects/shortage-radar/branches/production/endpoints/primary")
a, _ = p.parse_known_args()
C, spark, w = a.catalog, SparkSession.builder.getOrCreate(), WorkspaceClient()

cred = w.postgres.generate_database_credential(endpoint=a.endpoint)
host = w.postgres.get_endpoint(name=a.endpoint).status.hosts.host
with psycopg.connect(host=host, dbname="databricks_postgres", user=w.current_user.me().user_name,
                     password=cred.token, sslmode="require") as conn:
    actions = pd.read_sql("""SELECT action_id, disruption_id, sku_id, region, action_type, description,
        est_revenue_protected::double precision AS est_revenue_protected, proposed_by, proposed_source, on_behalf_of,
        proposed_at, status, decided_by, decided_at, decision_rationale FROM decisions.mitigation_action""", conn)
    audit = pd.read_sql("SELECT audit_id, action_id, event, actor, at, details::text AS details FROM decisions.audit_log", conn)

spark.sql(f"""CREATE TABLE IF NOT EXISTS {C}.gold.mitigation_decision (
  action_id BIGINT, disruption_id STRING, sku_id STRING, region STRING, action_type STRING, description STRING,
  est_revenue_protected DOUBLE MASK {C}.governance.mask_commercial, proposed_by STRING, proposed_source STRING,
  on_behalf_of STRING, proposed_at TIMESTAMP, status STRING, decided_by STRING, decided_at TIMESTAMP, decision_rationale STRING)
  WITH ROW FILTER {C}.governance.region_filter ON (region)
  COMMENT 'Mitigation proposals and decisions from the Lakebase workflow (latest state per action)'""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {C}.gold.mitigation_audit (
  audit_id BIGINT, action_id BIGINT, event STRING, actor STRING, at TIMESTAMP, details STRING)
  COMMENT 'Append-only audit trail of the Lakebase mitigation workflow'""")

merged = 0
if len(actions):
    spark.createDataFrame(actions).createOrReplaceTempView("src_actions")
    spark.sql(f"""MERGE INTO {C}.gold.mitigation_decision t USING src_actions s ON t.action_id = s.action_id
                  WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *""")
    merged = len(actions)
appended = 0
if len(audit):
    spark.createDataFrame(audit).createOrReplaceTempView("src_audit")
    appended = spark.sql(f"""INSERT INTO {C}.gold.mitigation_audit SELECT s.* FROM src_audit s
        LEFT ANTI JOIN {C}.gold.mitigation_audit t ON t.audit_id = s.audit_id""").first()[0]
summary = {"task": "land_decisions", "actions_merged": merged, "audit_rows_appended": int(appended),
           "status_counts": actions["status"].value_counts().to_dict() if len(actions) else {}}
os.makedirs(f"/Volumes/{C}/raw/run_log", exist_ok=True)
with open(f"/Volumes/{C}/raw/run_log/land_decisions.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary))
