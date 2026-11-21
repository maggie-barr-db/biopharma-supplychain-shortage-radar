# BUILD_LOG.md

| Date | What I tried | What failed | What I changed and why |
|---|---|---|---|
| 2026-11-21 | Wrote FEBAR_CONTEXT.md and USE_CASE.md with the AI assistant from the FE Bar guide prompts; approved both | - | Added evaluator read limits (30 files, 9K chars per file) to the context so the repo stays small |
| 2026-11-21 | `databricks catalogs create supply_chain` via CLI | Metastore has no storage root; CLI cannot create a Default Storage catalog | Created the catalog with SQL `CREATE CATALOG` on the serverless warehouse, which uses Default Storage; created schemas raw, bronze, silver, gold, ml, governance |
| 2026-11-21 | Checked region support for agents and Lakebase (Azure centralus) | Docs now list Knowledge Assistant and Supervisor Agent as legacy; Genie spaces renamed Genie Agents | Planned routing around Genie Agents plus Genie One or an Agent Bricks CLI code agent instead of the Supervisor |
| 2026-11-21 | Chose build decisions 1-12 and wrote BUILD_PLAN.md, DECISIONS.md and EVAL_PROTOCOL.md (eval rules fixed before any results) | - | Picked FastAPI + React over Streamlit for long-term reuse |
