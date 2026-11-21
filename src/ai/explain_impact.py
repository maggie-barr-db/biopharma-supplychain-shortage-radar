"""P04 GenAI step: ai_query writes a planner-ready explanation for each at-risk SKU in an active disruption,
then a deterministic groundedness check, logged to MLflow, verifies it (EVAL_PROTOCOL.md section 3: every number must come from the row).

Explanations use units, days and dates only (never price or revenue), so planners can read them without a
commercial leak; ml.impact_explanation carries the same region row filter as gold.
"""
import argparse, json, os, re

import mlflow
from pyspark.sql import SparkSession

p = argparse.ArgumentParser()
p.add_argument("--catalog", default="supply_chain")
p.add_argument("--llm", default="databricks-claude-haiku-5-5")
p.add_argument("--limit", type=int, default=25)
a, _ = p.parse_known_args()
spark = SparkSession.builder.getOrCreate()
C = a.catalog

spark.sql(f"""
CREATE OR REPLACE TABLE {C}.ml.impact_explanation COMMENT 'ai_query explanations of disruption impact (units and days only)' AS
WITH rows AS (
  SELECT disruption_id, sku_id, drug, region, site_id, api_id, single_source, round(weekly_units, 0) AS weekly_units,
         round(cover_days_before, 1) AS cover_days_before, round(cover_days_without_vendor, 1) AS cover_days_without_vendor,
         requalification_days, projected_stockout_date, round(supply_gap_days, 1) AS supply_gap_days
  FROM {C}.silver.impact_base
  WHERE event_date = (SELECT max(event_date) FROM {C}.silver.impact_base)
  ORDER BY supply_gap_days DESC, projected_stockout_date LIMIT {a.limit})
SELECT *, ai_query('{a.llm}', concat(
  'You are a pharmaceutical supply planner. In 2 sentences, explain the supply risk for this SKU to a planning lead and ',
  'name the single most useful next step. Use ONLY numbers and dates that appear in the data. Never mention price or revenue. Data: ',
  to_json(named_struct('sku_id', sku_id, 'drug', drug, 'region', region, 'api_id', api_id, 'single_source', single_source,
    'weekly_units', weekly_units, 'days_of_cover_now', cover_days_before, 'days_of_cover_without_vendor', cover_days_without_vendor,
    'days_to_qualify_alternate_source', requalification_days, 'projected_stockout_date', projected_stockout_date,
    'supply_gap_days', supply_gap_days)))) AS explanation,
  '{a.llm}' AS llm, current_timestamp() AS generated_at
FROM rows""")
spark.sql(f"ALTER TABLE {C}.ml.impact_explanation SET ROW FILTER {C}.governance.region_filter ON (region)")

df = spark.table(f"{C}.ml.impact_explanation").toPandas()
NUM = re.compile(r"\d[\d,]*\.?\d*")


def allowed_numbers(row):
    vals = set()
    for k in ("weekly_units", "cover_days_before", "cover_days_without_vendor", "requalification_days", "supply_gap_days"):
        v = float(row[k])
        vals |= {f"{v:g}", f"{round(v):g}", f"{v:.1f}", f"{int(v):,}", f"{int(v)}"}
    vals |= set(NUM.findall(f"{row['projected_stockout_date']} {row['sku_id']} {row['api_id']} {row['site_id']} {row['drug']}"))
    return vals


def grounded(inputs, outputs) -> bool:
    """True when every number in the explanation appears in the source row."""
    found = {n.rstrip(".,") for n in NUM.findall(outputs)}  # drop trailing sentence punctuation
    return found <= inputs["allowed"]


data = [{"inputs": {"sku_id": r["sku_id"], "allowed": allowed_numbers(r)}, "outputs": r["explanation"]} for _, r in df.iterrows()]
user = spark.sql("SELECT current_user() u").first().u
mlflow.set_experiment(f"/Users/{user}/shortage-radar-late-po")
results = [grounded(inputs=d["inputs"], outputs=d["outputs"]) for d in data]
with mlflow.start_run(run_name="impact_explanations_groundedness"):
    mlflow.log_metrics({"explanations": len(results), "grounded": sum(results), "grounded_rate": sum(results) / max(len(results), 1)})
    mlflow.log_param("llm", a.llm)
summary = {"task": "explain_impact", "llm": a.llm, "explanations": len(results), "grounded": sum(results),
           "ungrounded_skus": [d["inputs"]["sku_id"] for d, ok in zip(data, results) if not ok],
           "sample": [{"sku_id": r["sku_id"], "explanation": r["explanation"]} for _, r in df.head(3).iterrows()]}
os.makedirs(f"/Volumes/{C}/raw/run_log", exist_ok=True)
with open(f"/Volumes/{C}/raw/run_log/explain_impact.json", "w") as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary))
