# FEBAR_CONTEXT.md

Read this before every task and follow it. It overrides tool defaults.

## 1. Purpose

I am building my own FE Bar submission: a working prototype that solves a supply chain problem for a biopharma company in life sciences.

- **Customer (fictional):** BioChain Industries, a mid-size biopharma manufacturer.
- **Problem:** a single-source active pharmaceutical ingredient (API) supplier fails an FDA inspection or goes offline. Planners need to know which finished drugs, lots and markets are exposed, how many days of cover remain, and what to do, before a shortage hits patients.
- **Executive sponsor:** VP Supply Chain. KPIs: revenue at risk, stockout days avoided, mitigation cost, OTIF, single-source exposure.
- **Domain owner:** Supply Planning Lead. KPIs: time to impact assessment, time to mitigation decision, days of cover, predicted late POs, second-source readiness.
- **Compliance KPIs:** decision audit completeness (Part 11 style), FDA shortage notification timeliness, supplier quality signals.

## 2. Non-negotiable FE Bar rules

- One connected journey starting from RAW synthetic or public data: Lakeflow ingest, Unity Catalog governance, Lakebase operational serving, ML or GenAI, a Genie agent, a Databricks App. Each stage consumes the output of the previous one. No disconnected demos.
- The evaluator reads TEXT only. Every stage needs committed text evidence that it ran: notebook outputs, run logs, query results, model output. Screenshots and recordings do not count. Source code alone fails the Build domain.
- The GitHub repo must be readable by the evaluator: public on the personal (non-EMU) account.
- Synthetic or public data only. Never real customer data, customer names, people's names, internal system names or logos, in code, data, docs, commit messages or the deck.
- This is my own work. Never use or imitate Solution Builder output and never copy another person's build.
- A business deck (PDF, .txt or .md) and an AI role-play are also required; we prepare those at the end.

## 3. What the evaluator can read (design for this)

- At most **30 files, 9,000 characters per file (head only, the rest is cut), 90,000 characters total**.
- Browser upload keeps only `.py .ipynb .sql .md .txt .json .csv`. Never use `.log`, `.out` or `.jsonl` for evidence.
- Ranking favours `.ipynb`, then `.sql`, then `.py`, then `VALIDATION.md`, then `.txt/.json`. About ten full-size source files exhaust the budget and the lowest-ranked files (usually evidence) get cut.
- So: keep the repo small and files short; put the proof (counts, metrics, "run complete") at the **top** of every evidence file; keep `VALIDATION.md` at the root mapping each of the six stages to its file and evidence.

## 4. How you work with me

- Work in small, verifiable steps. After each step: what you changed, how you verified it, what is next.
- STOP AND ASK before any decision about: the use case and story, personas, architecture and trade-offs, which data issues to plant, quality rules, access rules, AI approach, numbers in the value case, slide content and the narrative. Give two or three options with pros and cons and a recommendation; I decide.
- Keep BUILD_LOG.md: date, what you tried, what failed, what you changed and why. I will use it to write how I used AI.
- Record every decision I make in DECISIONS.md (decision, options considered, why). I will rewrite it in my own words.
- Mark every narrative, opinion and decision section you draft (README, DECISIONS.md, deck notes) with [YOUR WORDS] so I rewrite it myself. The use case, the decisions, the numbers and the words must be mine.
- Never print, log or commit tokens, passwords or connection strings. Never guess a Databricks CLI profile; ask me.
- Industry facts and numbers must be cited or marked [ASSUMPTION] / [CHECK]. Never invent a statistic.
- Commits are made by the AI assistant under my git identity (maggie.barrett@databricks.com, linked to the maggie-barr-db GitHub account), in small commits as we go. The evaluator verifies the commit author username, so never commit under any other identity.

## 5. Engineering conventions

- Workspace: ask me for the workspace URL and CLI profile, then use `--profile <name>` on every CLI command.
- Everything lives in Unity Catalog catalog `supply_chain`, with schemas `raw` (UC volume for landed files), `bronze`, `silver`, `gold`, `ml` and `governance` (mask and filter functions, entitlement mapping). Workspace: Azure FEVM `adb-7405619902341965.5.azuredatabricks.net`.
- Deploy everything with a Declarative Automation Bundle: `databricks.yml` with variables (catalog, schema, warehouse_id, model endpoints) and one target; `resources/*.yml` for pipelines, jobs and apps. Commands: `databricks bundle validate`, `databricks bundle deploy`, `databricks bundle run <resource>`. Anything bundles cannot deploy goes in a small script under `tools/`, called out in DECISIONS.md.
- Prefer serverless compute: serverless Lakeflow pipelines, serverless jobs, a serverless SQL warehouse.
- Pipelines in SQL (Lakeflow Spark Declarative Pipelines) unless Python is clearly better.
- Reruns must be safe (idempotent): no duplicate rows when a step runs twice.
- Every notebook task ends with `dbutils.notebook.exit(json.dumps(summary))`, a short JSON of what it did (rows, IDs, pass counts). Python file tasks print the same summary. The evidence step reads these back, because `.py` notebooks carry no outputs in the repo.
- If Databricks agent skills are installed, load the matching skill before each product (pipelines, Unity Catalog, Lakebase, apps, Genie, MLflow, jobs, bundles) and follow it.

**Decided scope (2026-11-21):**
- Security without governed tags (this workspace has none left): classic UC column masks and row filters via SQL functions; ABAC with governed tags is the production path, noted in DECISIONS.md.
- Apps and agents run on behalf of the user (OBO). UC policies do not reach Lakebase, so Lakebase access is enforced with Postgres grants or row-level security.
- Lakebase holds the mitigation workflow: proposed action, approver, timestamp, rationale, audit trail.
- Current product names (Nov 2026): Genie spaces are now **Genie Agents**; Knowledge Assistant and Supervisor Agent are **legacy** (do not use). Routing across agents uses Genie One or a code agent built with the Agent Bricks CLI. Workspace region: Azure centralus (Lakebase Autoscaling supported).
- Out of scope: Delta Sharing, Genie Workbench Auto-Optimize, CI pipeline (next step).

## 6. Repository layout

README.md, FEBAR_CONTEXT.md, VALIDATION.md, USE_CASE.md, BUILD_PLAN.md, EVAL_PROTOCOL.md, DECISIONS.md, BUILD_LOG.md, databricks.yml, resources/, src/data/, src/pipeline/, src/governance/, src/ai/, src/serve/, src/genie/, src/app/, tools/, evidence/, deck/. Keep the evaluator-readable total under 30 files. Add .gitignore entries for .databricks/, .env, *.pem, notes/ (local working notes) and any credentials.

## 7. Definition of done for every task

Code committed, deployed, run successfully in the workspace, verified with a query or API call whose output you show me, and a line added to BUILD_LOG.md.
