# DECISIONS.md

[REWRITE IN YOUR WORDS] Every entry below was decided by me on 2026-11-21 from options my AI assistant laid out. Rewrite the "why" in your own words before submitting.

| # | Decision | Chosen | Alternatives considered | Why |
|---|---|---|---|---|
| 1 | Ingestion | Auto Loader (`read_files`) over files in a UC volume | Lakeflow Connect to a live source; JDBC | Files mirror how ERP and quality extracts really arrive, and a file-arrival trigger shows the pipeline reacting to a new disruption signal. Lakeflow Connect would be the production path for SAP |
| 2 | Sources | Two systems merged (ERP + supplier quality) | One source | Supplier codes that do not match ERP vendor IDs is the real reason impact takes days; conforming them is the core of the story |
| 3 | Data quality | Quarantine duplicate PO lines and negative forecasts; warn on missing lead times; fail on null keys or schema breaks | Drop everything bad; warn only | Bad rows must not change days of cover, but planners need to see them; a broken feed should stop, not silently publish |
| 4 | Personas | `planner_us`, `planner_eu` (own region, cost masked), `supply_exec` (all regions, cost visible, approves) | Two groups only | Matches how regional planning teams and the VP actually split, and gives a visible mask and filter difference |
| 5 | Access test identity | Service principal in `planner_eu` | A second human user | Scriptable and repeatable, so the test output can be committed as evidence |
| 6 | Lakebase pattern | Synced table from gold for reads + native Postgres tables for decisions and audit | Synced only; job upserts only | Synced tables are read-only, and human decisions need transactional writes that the pipeline must never overwrite |
| 7 | Intelligent step | Trained late-PO classifier + `ai_query` explanations and mitigation drafts | Score + ai_query only; model only | The model changes the numbers (projected days of cover); the LLM changes the workflow (drafts what a planner would write). AI influences decisions, not decoration |
| 8 | AI evaluation | Time-split holdout vs baseline; 15-question Genie benchmark; MLflow judges on explanations | Manual spot checks | Gives numbers a technical buyer can challenge; see EVAL_PROTOCOL.md |
| 9 | App | FastAPI + React, Databricks-branded | Streamlit | Built to be a reusable asset; React gives a production-grade UI and clean API separation |
| 10 | Trigger | File arrival on `landing/supplier_quality/` + manual | Schedule | A new warning letter should start the refresh, not wait for a nightly run |
| 11 | Routing | Code agent from the Agent Bricks CLI using two Genie Agents and a `propose_mitigation` Lakebase tool, with request-user auth and MLflow tracing | Genie One across both agents; one Genie Agent with a docs volume | Supervisor Agent and Knowledge Assistant are now legacy. A code agent makes routing testable and traced, and lets the AI act by proposing a mitigation a human approves |
| 12 | Security model | Classic UC column masks and row filters | ABAC with governed tags | The workspace has no governed tags left; ABAC is the production path to scale the same rules across tables. UC policies do not reach Lakebase, so Lakebase uses Postgres RLS |
