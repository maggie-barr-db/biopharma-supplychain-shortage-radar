# BUILD_PLAN.md - API shortage radar

Catalog `supply_chain`. Workspace: Azure centralus FEVM. Serverless everywhere. Decisions in DECISIONS.md, evaluation rules in EVAL_PROTOCOL.md.

## 1. Data flow

```
P01 src/data/generate.py (job task, seeded, idempotent: overwrites a dated drop folder)
  -> /Volumes/supply_chain/raw/landing/
       erp/{vendors,materials,bom,po_lines,inventory}/   CSV, PO lines re-sent with duplicates, kg/g mix
       supplier_quality/                                 JSON, supplier_code != ERP vendor_id, free-text findings
       forecast/                                         CSV weekly, late and duplicate files, some negatives
       sku/                                              CSV SKU master with net price and region
       docs/                                             TXT inspection summaries and warning letters (for Genie)
P02 Lakeflow SDP (SQL, Auto Loader read_files, serverless, triggered)
  bronze.*   streaming tables, raw columns + _source_file + _load_ts
  silver.*   conformed; expectations; quarantine tables
  gold.*     materialized views + metric view
P03 Unity Catalog: governance.* functions -> column mask on cost, row filter on region
P04 ML: ml.late_po model (train job) -> serving endpoint -> gold.po_risk_score (batch score task)
    gold.days_of_cover reads po_risk_score; ai_query writes gold.impact_explanation
P05 Access test: service principal in planner_eu runs tools/access_test.py -> evidence
P06 Lakebase Autoscaling project shortage-radar
    synced table  <- gold.disruption_impact      (read path)
    native tables  mitigation_action, audit_log  (write path, Postgres RLS by region)
P07 Genie Agents: "Supply Exposure" (gold + metric view), "Supplier Quality" (silver.supplier_event + docs volume)
P08 Routing agent (Agent Bricks CLI, OpenAI Agents SDK template): tools = 2 Genie Agents + propose_mitigation (Lakebase insert)
P09 App (FastAPI + React, Databricks-branded, OBO): Radar, Impact detail, Approvals, Ask
P10 Evidence: tools/capture_evidence.py reads job exits, queries, endpoint and agent responses -> evidence/*.md
```

## 2. Stages

| Stage | For the Supply Planning Lead | Inputs -> outputs | Features | Verified by -> evidence |
|---|---|---|---|---|
| Lakeflow | One trusted copy of ERP and supplier quality, with supplier codes matched | landing files -> bronze, silver, gold | SDP SQL, Auto Loader, expectations, quarantine, file-arrival trigger | row counts per layer, expectation pass/drop counts -> evidence/01_pipeline.md |
| Unity Catalog | Each region sees its own sites; cost hidden from planners | gold.* -> masked, filtered views of the same tables | column mask + row filter functions, groups, lineage | same query as exec vs planner_eu SP -> evidence/02_governance.md |
| ML / GenAI | Know which API orders will be late; get the impact in plain words | silver.po_line -> ml model -> gold.po_risk_score, gold.impact_explanation | MLflow 3, UC registry, Model Serving, ai_query | holdout metrics vs baseline, endpoint response, sample explanations -> evidence/03_ml.md |
| Lakebase | Propose, approve and audit mitigations in one place | gold.disruption_impact (synced) -> mitigation_action, audit_log | Lakebase Autoscaling, synced table, Postgres RLS | insert, approve, read-back as two roles -> evidence/04_lakebase.md |
| Genie + routing | Ask "which products run out first if supplier X stops?" | gold + metric view + docs -> answers, proposed mitigations | Genie Agents, Conversation API, Agent Bricks CLI, request-user auth, MLflow tracing | 15-question benchmark, routing accuracy, traces -> evidence/05_genie_agent.md |
| App | One screen from signal to decision | Lakebase + agent + Genie -> UI | Databricks Apps (FastAPI + React), OBO | health check and API responses per screen -> evidence/06_app.md |

## 3. Tables (grain)

**bronze** (as landed + `_source_file`, `_load_ts`): `vendor`, `material`, `bom`, `po_line`, `inventory`, `supplier_event`, `forecast`, `sku`.

**silver**
- `vendor` - one row per ERP vendor, with `supplier_code` from the xref (conformed).
- `material`, `bom` - one row per material; one row per SKU x API component.
- `po_line` - one row per PO line (duplicates removed, kg normalised); `po_line_quarantine`.
- `inventory` - one row per material or SKU x site x snapshot date.
- `forecast` - one row per SKU x region x week, latest file wins; `forecast_quarantine`.
- `sku` - one row per SKU, active only.
- `supplier_event` - one row per quality event, mapped to vendor_id.

**gold** (five, plus scores)
- `api_exposure` - one row per API x SKU x region; single-source flag (the ontology edges).
- `days_of_cover` - one row per SKU x region; on hand, inbound adjusted by late-PO risk, demand.
- `supplier_risk` - one row per vendor; latest quality status and mean late-PO risk.
- `disruption_impact` - one row per active disruption x SKU x region; stockout date, revenue at risk.
- `mv_supply_kpis` - metric view: days of cover, revenue at risk, single-source exposure, OTIF.
- `po_risk_score`, `impact_explanation` - model and ai_query outputs.

## 4. Bundle layout

`databricks.yml` variables: `catalog`, `warehouse_id`, `lakebase_project`, `model_endpoint`, `llm_endpoint`; one target `dev` (profile set by the user). `resources/`: `pipeline.yml` (SDP), `jobs.yml` (`radar_main`, `radar_train`), `lakebase.yml` (project, synced table), `apps.yml` (`shortage-radar-app`). Genie Agents and the routing agent: try bundle resources first; otherwise `tools/deploy_genie.py` and `agentbricks deploy`, noted in DECISIONS.md. Note: the evaluator drops `.yml` files, so VALIDATION.md quotes the key bundle settings.

## 5. Orchestration

Job `radar_main`, file-arrival trigger on `landing/supplier_quality/`, plus manual: `generate` (manual runs only) -> `pipeline` -> `score_po_risk` -> `refresh_gold_impact` -> `explain_impact` -> `sync_lakebase` -> `capture_evidence`. Job `radar_train`: manual, trains and registers the model, updates the endpoint.

## 6. Time plan (~9 h)

| Block | Hours |
|---|---|
| P01-P02 generator + pipeline | 2.0 |
| P03 + P05 governance + access test | 0.5 |
| P04 ML + ai_query | 1.0 |
| P06 Lakebase | 1.0 |
| P07-P08 Genie Agents + routing agent | 2.0 |
| P09 React app | 1.5 |
| P10 evidence, VALIDATION.md, README | 1.0 |

## 7. Repo size budget

The evaluator reads 30 files and drops `.tsx/.css/.yml`. Readable files planned: 9 docs, ~13 source (`.py`, `.sql`), 4-6 evidence `.md`. React source is kept, but the app's logic lives in the FastAPI `.py` so the evaluator can read it.

## 8. Risks

- **OBO from app to agent to Genie** may not chain; fallback is that the app calls Genie Conversation API OBO directly and the agent uses its service principal for the Lakebase tool only.
- **Lakebase RLS identity:** the app connects as its service principal and sets the region from the OBO user; documented as a trade-off.
- **Genie Agents volumes** are Public Preview; if unavailable, the Supplier Quality agent uses `silver.supplier_event` text columns only.
