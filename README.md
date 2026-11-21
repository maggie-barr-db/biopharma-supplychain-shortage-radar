# API Shortage Radar for BioChain Industries

**When a single-source API supplier fails an FDA inspection, BioChain's planners see every exposed product, market and stockout date in minutes instead of 3-5 days, and every mitigation is proposed, approved and audited in one place.** [YOUR WORDS]

BioChain Industries is a fictional mid-size biopharma manufacturer (synthetic data only): 288 active SKUs across US, EU and APAC, $1.87B revenue, 43% of it dependent on single-source APIs.

## The result on the demo disruption

An FDA Warning Letter lands for supplier V100103 (Larchmont Synthesis). Within one pipeline run:

- **29 SKUs exposed**, 25 single-source (morphine, midazolam and others), across all three regions.
- **First projected stockout 2027-01-11**, 52 days out; 21 SKUs run out before an alternate source can be qualified (180 days assumed).
- **$30.0M revenue at risk** of $187M annual revenue exposed; the VP sees it, planners see units and days only.
- The routing agent answers "which products are exposed to the supplier that just got a warning letter?" by asking the Supplier Quality agent first and the Supply Exposure agent second, then proposes a mitigation that a supply executive must approve.

Value hypothesis (USE_CASE.md section 6): about **$7.8M a year** from fewer stockout days, lower expedite cost and planner time. [YOUR WORDS]

## Who it is for

| Persona | Question they bring | What they get |
|---|---|---|
| VP Supply Chain (sponsor) | How much revenue is at risk and are we on top of it? | Revenue at risk, single-source exposure, approved decisions with an audit trail |
| Supply Planning Lead (owner) | Which SKUs run out first and what do we do? | Days of cover with risk-adjusted inbound, stockout dates, a place to propose actions |

## How it works (one connected journey)

```
synthetic ERP + supplier quality + forecast files (UC volume)
  -> Lakeflow SDP (Auto Loader, expectations, quarantine)  bronze -> silver -> gold
  -> Unity Catalog: published gold layer with region row filter and commercial column masks
  -> ML: late-PO model (MLflow, UC registry, serving endpoint) scores open POs -> feeds days of cover
  -> GenAI: ai_query impact explanations; routing agent (Agent Bricks CLI) over two Genie Agents
  -> Lakebase: synced impact + entitlements; native mitigation workflow with RLS, approval rules, audit log; decisions land back in Delta
  -> Databricks App (FastAPI + React), on behalf of the signed-in user: Radar, Impact, Approvals, Ask
```

Each stage reads the previous one: the model's scores change gold days of cover, gold impact is synced into Lakebase, the app and agent write decisions back to Lakebase, and Genie answers from the governed gold layer.

## Where the proof is

See **VALIDATION.md** for stage -> file -> evidence. Evidence notebooks with real outputs are in `evidence/`.

## Decisions and trade-offs

See **DECISIONS.md** (12 decisions with alternatives). The ones a technical buyer will ask about:

- **Classic row filters and masks instead of governed-tag ABAC** because the demo workspace has no governed tags left; ABAC is the production path.
- **UC policies do not reach Lakebase**, so the same entitlements are enforced again with Postgres RLS and approval triggers.
- **Supervisor Agent and Knowledge Assistant are legacy** (Nov 2026 docs), so routing is a code agent from the Agent Bricks CLI using Genie Agents as tools, with request-user (OBO) auth and MLflow tracing.
- **The late-PO model only counts if it beats a simple baseline** on a time-split holdout (EVAL_PROTOCOL.md). It did: PR-AUC 0.562 vs 0.455.
- **Agents are graded, not trusted:** Genie answered 11 of 12 benchmark questions correctly, the routing agent picked the right tools 15 of 15 times, and 25 of 25 ai_query explanations used only numbers from their source row.
- **App-to-agent token forwarding was refused** (app-to-app OBO), so Ask in the app falls back to the Supply Exposure Genie Agent as the user and says so; the agent is called directly with the user's token in the evaluation.

## Deploy into a new workspace

```
databricks bundle deploy --profile <p>            # catalog, schemas: see tools/run_sql.py notes below
databricks bundle run radar_rebuild --profile <p>  # generate, full refresh, train, score, explain, sync
python tools/run_sql.py src/governance/policies.sql ...   # entitlements, filter and mask functions
python tools/pg.py --profile <p> --file src/serve/lakebase_setup.sql
cd src/agent && agentbricks deploy                 # routing agent (not a bundle resource yet)
databricks bundle run radar_app --profile <p>
databricks bundle run radar_main --params scenario=warning_letter   # the demo disruption
```

The catalog is created with SQL (`CREATE CATALOG supply_chain`) because workspaces on Default Storage reject catalog creation from the CLI.

## How I used AI

Built with an AI coding assistant (Claude Code) as a pair engineer, following the FE Bar guide prompts: it drafted code, SQL and docs; I made every use-case, architecture, data-quality, access and AI decision (DECISIONS.md) and the evaluation rules before any results (EVAL_PROTOCOL.md). BUILD_LOG.md records what failed and what we changed. [YOUR WORDS]
