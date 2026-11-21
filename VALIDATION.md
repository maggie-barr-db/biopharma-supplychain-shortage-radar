# VALIDATION.md - stage -> code -> evidence

Every stage below ran in an Azure Databricks workspace (centralus) on 2026-11-21. Evidence files in `evidence/` are notebooks
with real captured outputs (queries, job summaries, endpoint and agent responses), written by `tools/capture_evidence.py`
and `tools/eval_genie.py`. Headline result first in each.

| # | Stage | What it does | Code | Evidence |
|---|---|---|---|---|
| 1 | Lakeflow | Auto Loader ingests ERP, supplier quality, forecast and SKU files; conforms supplier codes; quarantines duplicate POs and negative forecasts; fills missing lead times; builds gold | `src/data/generate.py`, `src/pipeline/bronze.sql`, `silver.sql`, `silver_calc.sql`, `gold.sql` | `evidence/01_pipeline.ipynb` |
| 2 | Unity Catalog | Published gold layer with region row filter and commercial masks; entitlement table, deny by default; planners granted gold only | `src/governance/policies.sql`, `grants.sql`, `src/pipeline/gold.sql` | `evidence/02_governance.ipynb` (same query as supply exec vs planner_eu service principal) |
| 3 | ML | Late-PO classifier with point-in-time features, time-split holdout vs baseline, UC registry, serving endpoint; scores feed gold days of cover | `src/ai/features.py`, `train_late_po.py`, `score_po_risk.py` | `evidence/03_ml.ipynb` (PR-AUC 0.562 vs baseline 0.455) |
| 3b | GenAI | `ai_query` explanations of each at-risk SKU (units and days only), groundedness checked and logged to MLflow | `src/ai/explain_impact.py` | `evidence/03_ml.ipynb`, `evidence/05_genie_agent.ipynb` |
| 4 | Lakebase | Synced impact and entitlements from UC; native mitigation workflow with Postgres RLS, approval rules (entitled approver, no self-approval, rationale) and append-only audit log | `src/serve/lakebase_setup.sql`, `lakebase_grants.sql`, `sync_lakebase.py` | `evidence/04_lakebase.ipynb` |
| 5 | Genie Agents + routing | Two Genie Agents (Supply Exposure with metric view; Supplier Quality with docs volume); routing agent (Agent Bricks CLI, OpenAI Agents SDK) with request-user auth and a `propose_mitigation` Lakebase tool | `src/genie/*.geniespace.json`, `metric_view.sql`, `src/agent/agent/agent.py`, `src/agent/agent/tools/propose_mitigation.py` | `evidence/05_genie_agent.ipynb` (benchmark correctness, routing accuracy, planner access check) |
| 6 | Databricks App | FastAPI + React app on behalf of the signed-in user: Radar, Impact, Approvals, Ask | `src/app/backend/main.py` (logic), `src/app/frontend/src/App.tsx` (UI) | `evidence/06_app.ipynb` (API responses per screen) |

## How the stages connect

- `ml.po_risk_score` (stage 3) is joined into `silver.cover_base` and `silver.impact_base`, so the model changes gold days of cover and revenue at risk.
- `silver.impact_base` (stage 1) is synced to Lakebase `ops.disruption_impact` (stage 4); the app and agent write `ops.mitigation_action` against it.
- Genie and the app read only the governed gold layer (stage 2); the planner identity sees EU rows and NULL revenue in both.
- The demo signal is a file: `radar_main --params scenario=warning_letter` drops one supplier quality file; the job runs pipeline, score, refresh, explain and Lakebase sync.

## Bundle (the evaluator does not read .yml, so key settings are quoted here)

```
databricks.yml   variables: catalog=supply_chain, warehouse_id; target dev
resources/pipeline.yml   serverless SDP, libraries bronze.sql, silver.sql, silver_calc.sql, gold.sql
resources/jobs.yml       radar_main: should_generate? -> generate -> pipeline -> score_po_risk -> refresh_gold -> explain_impact, sync_lakebase
                         (file-arrival trigger on landing/supplier_quality/); radar_rebuild: generate -> full refresh -> train -> score -> refresh -> explain, sync
                         radar_train: train_late_po (registers supply_chain.ml.late_po_model@champion, updates endpoint late-po-model)
resources/lakebase.yml   postgres_projects shortage-radar (PG 17); postgres_synced_tables ops.disruption_impact, ops.user_entitlement (SNAPSHOT)
resources/genie.yml      genie_spaces supply_exposure, supplier_quality (serialized space v2 files)
resources/apps.yml       app shortage-radar, user_api_scopes [sql, dashboards.genie], resources: warehouse, Genie Agent, Lakebase (CAN_CONNECT_AND_CREATE)
resources/volumes.yml    raw.landing, raw.run_log
```

The routing agent deploys with `agentbricks deploy` from `src/agent` (agent.toml binds both Genie Agents with `auth = "user"`).
