# VALIDATION.md - reviewer map: stage -> code -> evidence

Start here, then `evidence/00_overview.ipynb`. Everything ran in an Azure Databricks workspace (centralus) on 2026-11-21. Evidence notebooks hold real captured outputs (queries, job summaries, event-log metrics, endpoint, agent and app responses), headline first.

| # | Stage | What it does | Code | Evidence and result |
|---|---|---|---|---|
| 1 | Lakeflow | Auto Loader under a schema contract (unexpected fields rescued and warned); conforms supplier codes; quarantines duplicate POs and negative forecasts; fills missing lead times; tracks feed freshness; fails the update on missing keys; file-arrival trigger | `src/pipeline/bronze.sql`, `silver.sql`, `silver_calc.sql`, `gold.sql`, `src/data/generate.py` | `01_pipeline`: 954 duplicates quarantined, 42 negatives dropped, 60/60 suppliers matched, schema drift rescued, triggered run SUCCESS |
| 2 | Unity Catalog | Published gold layer with region row filter and commercial masks; entitlement table, deny by default; planners granted gold only | `src/governance/policies.sql`, `src/pipeline/gold.sql` | `02_governance`: exec sees 3 regions and revenue; EU planner sees EU only, revenue NULL, silver denied |
| 3 | ML | Late-PO classifier with point-in-time features; time-split holdout vs baseline; UC registry; serving endpoint; scores feed gold days of cover | `src/ai/features.py`, `train_late_po.py`, `score_po_risk.py` | `03_ml`: PR-AUC 0.562 vs 0.455 baseline; endpoint 0.73 vs 0.06 for risky vs reliable vendor |
| 3b | GenAI | `ai_query` explanations per at-risk SKU (units and days only), groundedness checked and logged to MLflow | `src/ai/explain_impact.py` | `03_ml`: 25 of 25 grounded |
| 4 | Lakebase | Synced impact and entitlements; native workflow with Postgres RLS, approval rules (entitled approver, no self-approval, rationale), append-only audit, no deletes; decisions land back in governed Delta | `src/serve/lakebase_setup.sql`, `sync_lakebase.py`, `land_decisions.py` | `04_lakebase`: RLS blocks cross-region writes, rule violations refused, decision in `gold.mitigation_decision` |
| 5 | Genie + routing | Genie Agents Supply Exposure (gold + metric view) and Supplier Quality (events + docs volume); routing agent (Agent Bricks CLI, OpenAI Agents SDK) with request-user auth and a `propose_mitigation` Lakebase tool | `src/genie/*.geniespace.json`, `metric_view.sql`, `src/agent/agent/agent.py`, `src/agent/agent/tools/propose_mitigation.py` | `05_genie_agent`: Genie 11/12 correct, routing 15/15, planner sees EU only and NULL revenue |
| 6 | App | FastAPI + React on behalf of the signed-in user: Radar, Impact, Approvals, plus a chat dock on every page that keeps the conversation across pages and sends the page context (routes through the agent as the user) | `src/app/backend/main.py`, `src/app/frontend/src/App.tsx` | `06_app`: API responses per screen; Ask via agent -> Genie |

## Data flow

```
generate.py -> /Volumes/supply_chain/raw/landing/{erp, supplier_quality, forecast, sku, docs}
  -> bronze (9 streaming tables, Auto Loader, rescue mode) -> silver (conformed, quarantine, source_freshness)
  -> silver calc (exposure, cover, impact; reads ml.po_risk_score) -> gold (published: row filter + masks) + mv_supply_kpis
  -> Lakebase: ops.disruption_impact, ops.user_entitlement (synced) | decisions.mitigation_action, audit_log (native, RLS)
  -> gold.mitigation_decision, gold.mitigation_audit (landed back)
  -> Genie Agents + routing agent -> App
```

**Gold tables (grain):** `api_exposure` (API x SKU x region, the ontology edges), `days_of_cover` (SKU x region), `supplier_risk` (vendor), `supplier_event` (quality event), `disruption_impact` (disruption x SKU), `mitigation_decision` (action), metric view `mv_supply_kpis`.

## How the stages connect

- Model scores (`ml.po_risk_score`) feed silver calc, so the model changes gold days of cover and revenue at risk.
- `silver.impact_base` is synced into Lakebase; the app and agent write `decisions.mitigation_action`; `land_decisions` brings decisions back to Delta.
- Genie and the app read only the governed gold layer; the EU planner sees EU rows and NULL revenue in both, and in Lakebase via RLS.
- A new file in `landing/supplier_quality/` starts `radar_main`: pipeline -> score -> refresh gold -> explain + Lakebase sync -> land decisions.

## Bundle (the evaluator does not read .yml, so key settings are quoted)

```
databricks.yml           variables catalog=supply_chain, warehouse_id; target dev
resources/pipeline.yml   serverless SDP: bronze.sql, silver.sql, silver_calc.sql, gold.sql
resources/jobs.yml       radar_main (file-arrival trigger): should_generate? -> generate -> pipeline -> score_po_risk -> refresh_gold
                         -> explain_impact, sync_lakebase -> land_decisions; radar_rebuild (fresh workspace); radar_train
resources/lakebase.yml   postgres project shortage-radar (PG 17); synced tables ops.disruption_impact, ops.user_entitlement
resources/genie.yml      genie_spaces supply_exposure, supplier_quality
resources/apps.yml       app shortage-radar, user_api_scopes [sql, dashboards.genie, genie, apps]; warehouse, Genie, Lakebase resources
resources/volumes.yml    raw.landing, raw.run_log
```

Not bundle-managed (README deploy steps): UC setup SQL, Lakebase setup SQL, `agentbricks deploy` for the agent.
