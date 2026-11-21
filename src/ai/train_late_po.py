"""P04 train the late-PO model (job radar_train) and serve it.

Follows EVAL_PROTOCOL.md: baseline = 1 - vendor trailing on-time rate; holdout = most recent
3 months of labelable PO lines by order date; main measure PR-AUC; no claim if the model beats
the baseline by less than 0.05. Registers supply_chain.ml.late_po_model (alias champion) and
points the serving endpoint at the new version.
"""
import argparse, json, os, sys
from datetime import timedelta

import mlflow
import pandas as pd
from mlflow.models import infer_signature
from pyspark.sql import SparkSession
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from features import FEATURES_CAT, FEATURES_NUM, feature_sql  # noqa: E402


def recall_at_top(y, score, frac=0.2):
    df = pd.DataFrame({"y": y, "s": score}).sort_values("s", ascending=False)
    top = df.head(int(len(df) * frac))
    return round(top["y"].sum() / max(df["y"].sum(), 1), 3)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="supply_chain")
    p.add_argument("--endpoint", default="late-po-model")
    a, _ = p.parse_known_args()
    spark = SparkSession.builder.getOrCreate()
    as_of = spark.sql(f"SELECT max(snapshot_date) d FROM {a.catalog}.silver.inventory").first().d
    # Label is only observable once a line has had time to arrive; censor recent promised dates.
    cutoff = as_of - timedelta(days=45)
    df = spark.sql(feature_sql(a.catalog, f"receipt_date IS NOT NULL AND promised_date <= '{cutoff}'")).toPandas()
    df["is_late"] = df["is_late"].astype(int)
    split = df["order_date"].max() - timedelta(days=91)
    train, test = df[df["order_date"] < split], df[df["order_date"] >= split]

    model = Pipeline([
        ("prep", ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), FEATURES_CAT)], remainder="passthrough")),
        ("clf", HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=42)),
    ])
    X_cols = FEATURES_NUM + FEATURES_CAT
    mlflow.set_registry_uri("databricks-uc")
    user = spark.sql("SELECT current_user() u").first().u
    mlflow.set_experiment(f"/Users/{user}/shortage-radar-late-po")
    with mlflow.start_run(run_name="late_po_hgb") as run:
        model.fit(train[X_cols], train["is_late"])
        p_model = model.predict_proba(test[X_cols])[:, 1]
        p_base = 1 - test["vendor_on_time_rate_365d"]
        m = {"train_rows": len(train), "test_rows": len(test), "test_late_rate": round(test["is_late"].mean(), 3),
             "pr_auc_model": round(average_precision_score(test["is_late"], p_model), 3),
             "pr_auc_baseline": round(average_precision_score(test["is_late"], p_base), 3),
             "roc_auc_model": round(roc_auc_score(test["is_late"], p_model), 3),
             "roc_auc_baseline": round(roc_auc_score(test["is_late"], p_base), 3),
             "recall_top20_model": recall_at_top(test["is_late"].values, p_model),
             "recall_top20_baseline": recall_at_top(test["is_late"].values, p_base.values)}
        m["pr_auc_lift"] = round(m["pr_auc_model"] - m["pr_auc_baseline"], 3)
        m["claim"] = "model adds value" if m["pr_auc_lift"] >= 0.05 else "no claim: use baseline"
        mlflow.log_metrics({k: v for k, v in m.items() if isinstance(v, (int, float))})
        mlflow.log_params({"holdout_start": str(split), "label_cutoff": str(cutoff), "features": ",".join(X_cols)})
        sig = infer_signature(test[X_cols].head(50), p_model[:50])
        info = mlflow.sklearn.log_model(model, name="model", signature=sig, input_example=test[X_cols].head(3),
                                        registered_model_name=f"{a.catalog}.ml.late_po_model",
                                        pyfunc_predict_fn="predict_proba")
    client = mlflow.MlflowClient()
    version = info.registered_model_version
    client.set_registered_model_alias(f"{a.catalog}.ml.late_po_model", "champion", version)

    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput
    w = WorkspaceClient()
    entity = ServedEntityInput(entity_name=f"{a.catalog}.ml.late_po_model", entity_version=str(version),
                               workload_size="Small", scale_to_zero_enabled=True)
    if any(e.name == a.endpoint for e in w.serving_endpoints.list()):
        w.serving_endpoints.update_config(name=a.endpoint, served_entities=[entity])
    else:
        w.serving_endpoints.create(name=a.endpoint, config=EndpointCoreConfigInput(served_entities=[entity]))

    summary = {"task": "train_late_po", "mlflow_run_id": run.info.run_id, "model_version": version,
               "endpoint": a.endpoint, "holdout_start": str(split), **m}
    os.makedirs(f"/Volumes/{a.catalog}/raw/run_log", exist_ok=True)
    with open(f"/Volumes/{a.catalog}/raw/run_log/train_late_po.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(json.dumps(summary, default=str))


if __name__ == "__main__":
    main()
