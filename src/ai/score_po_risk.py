"""P04 score open PO lines with the champion late-PO model -> ml.po_risk_score.

gold.days_of_cover and gold.disruption_impact read these scores, so the model changes the
projected cover and revenue at risk. Idempotent: overwrites the score table on every run.
"""
import argparse, json, os, sys

import mlflow
from pyspark.sql import SparkSession, functions as F

# Serverless file tasks run via exec without __file__, so the job passes --src-dir.
_src = next((sys.argv[i + 1] for i, x in enumerate(sys.argv) if x == "--src-dir"), ".")
sys.path.append(_src)
from features import FEATURES_CAT, FEATURES_NUM, feature_sql  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="supply_chain")
    p.add_argument("--src-dir", default=".")
    a, _ = p.parse_known_args()
    spark = SparkSession.builder.getOrCreate()
    mlflow.set_registry_uri("databricks-uc")
    name = f"{a.catalog}.ml.late_po_model"
    version = mlflow.MlflowClient().get_model_version_by_alias(name, "champion").version
    model = mlflow.sklearn.load_model(f"models:/{name}@champion")
    df = spark.sql(feature_sql(a.catalog, "receipt_date IS NULL")).toPandas()
    X = df[FEATURES_NUM + FEATURES_CAT]
    df["p_late"] = model.predict_proba(X)[:, 1]
    df["baseline_p_late"] = 1 - df["vendor_on_time_rate_365d"]
    out = (spark.createDataFrame(df[["po_number", "po_line", "vendor_id", "material_id", "p_late", "baseline_p_late"]])
           .withColumn("po_line", F.col("po_line").cast("int"))
           .withColumn("model_version", F.lit(str(version)))
           .withColumn("scored_at", F.current_timestamp()))
    out.write.mode("overwrite").option("overwriteSchema", "false").saveAsTable(f"{a.catalog}.ml.po_risk_score")
    summary = {"task": "score_po_risk", "model_version": version, "open_po_lines_scored": len(df),
               "mean_p_late": round(float(df["p_late"].mean()), 3),
               "lines_p_late_over_0_5": int((df["p_late"] > 0.5).sum()),
               "mean_baseline_p_late": round(float(df["baseline_p_late"].mean()), 3)}
    os.makedirs(f"/Volumes/{a.catalog}/raw/run_log", exist_ok=True)
    with open(f"/Volumes/{a.catalog}/raw/run_log/score_po_risk.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
