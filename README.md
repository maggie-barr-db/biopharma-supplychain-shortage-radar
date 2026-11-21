# API Shortage Radar for BioChain Industries

**When an API supplier gets an FDA Warning Letter, BioChain's VP Supply Chain sees how much revenue is at risk, which products run out and when, and gets an approved, audited mitigation plan moving in minutes instead of 3-5 days, before patients feel the shortage.** On the demo disruption that is $30.0M of revenue at risk across 29 SKUs, with the first stockout 52 days out. It gives supply chain leadership an operational view of disruptions that will keep happening, and a way to route the mitigation to the right people when they do.

BioChain Industries is a fictional mid-size biopharma manufacturer (synthetic data only): 288 active SKUs across US, EU and APAC, $1.87B revenue, 43% of it dependent on single-source APIs.

## The result on the demo disruption

An FDA Warning Letter lands for supplier V100103 (Larchmont Synthesis). Within one pipeline run:

- **29 SKUs exposed**, 25 single-source (morphine, midazolam and others), across all three regions.
- **First projected stockout 2027-01-11**, 52 days out; 21 SKUs run out before an alternate source can be qualified (180 days assumed).
- **$30.0M revenue at risk** of $187M annual revenue exposed; the VP sees it, planners see units and days only.
- The routing agent answers "which products are exposed to the supplier that just got a warning letter?" by asking the Supplier Quality agent first and the Supply Exposure agent second, then proposes a mitigation that a supply executive must approve.

**About $7.8M a year (estimate for a fictional company).** BioChain's baseline is an assumption: last year one API disruption cost $18M in lost revenue and $1.5M in expedite and spot buys. The estimate assumes the radar cuts stockout days by 40% and expedite premiums by 30%, plus planner time (assumptions next to each number in USE_CASE.md section 6). The pattern is real:
- FDA's 2022 inspection of Intas Pharmaceuticals found data-integrity failures; production stopped and the US ran short of cisplatin and carboplatin in 2023 (FDA Warning Letter 320-23-20, July 28, 2023).
- 62% of drugs that went into shortage in 2013-2017 were tied to manufacturing or quality problems (FDA, *Drug Shortages: Root Causes and Potential Solutions*, 2019).
- Sales volume fell 28-35% after a shortage (ASPE Report to Congress, May 2023), and shortages cost US hospitals nearly $900M a year in labor (Vizient, 2025).

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
- **The late-PO model only counts if it beats a simple baseline** on a time-split holdout (DECISIONS.md, evaluation protocol). It did: PR-AUC 0.562 vs 0.455.
- **Agents are graded, not trusted:** Genie answered 11 of 12 benchmark questions correctly, the routing agent picked the right tools 15 of 15 times, and 25 of 25 ai_query explanations used only numbers from their source row.
- **The user's identity flows app -> agent -> Genie.** Forwarding a user token between two Databricks Apps needs the calling app to request the `apps` scope plus every scope the target app uses (`genie`); with those, Ask in the app runs through the routing agent as the signed-in user. If the agent is unavailable, the app falls back to the Supply Exposure Genie Agent as the user and says so.

## Deploy into a new workspace

```
databricks bundle deploy --profile <p>
databricks bundle run radar_rebuild --profile <p>  # generate, full refresh, train, score, explain, sync
python tools/db.py sql src/governance/policies.sql --profile <p> --warehouse <id> --var catalog=supply_chain ...  # entitlements, filters, masks, grants
python tools/db.py pg --profile <p> --file src/serve/lakebase_setup.sql   # then GRANT radar_app_rw TO each app/agent SP
cd src/agent && agentbricks deploy                 # routing agent (not a bundle resource yet)
databricks bundle run radar_app --profile <p>
databricks bundle run radar_main --params scenario=warning_letter   # the demo disruption
```

The catalog is created with SQL (`CREATE CATALOG supply_chain`) because workspaces on Default Storage reject catalog creation from the CLI.

## How I used AI

**AI was my teammate, not my autopilot.** I used an AI coding assistant (Claude Code) to accelerate the build, enrich the planning and check my choices against current documentation. I set the goal, the context and a plan for how we would work through it, asked it what I was missing, then corrected it, made every decision (DECISIONS.md) and had it research what I needed before building. It drafted the code and docs and executed the build; I did the thinking and reasoning.

**Where I steered it.** The AI was valuing speed to fit the FE Bar's estimated build time, so it simplified in places where the result would have been thin in front of a customer. I wanted something I could put in front of a customer tomorrow, so I chose:
- the supply chain use case over the pharmacovigilance option it recommended, because it interested me more
- React and FastAPI over Streamlit, so the app can become a reusable asset
- real schema-contract and freshness checks instead of rewording a data quality gap
- landing Lakebase decisions back into governed Delta, because approved mitigations matter outside the app
- fixing the app-to-agent call so the in-app chat routes through the agent, instead of accepting a fallback

**Iterating on the product.** Once the build ran, I went through the app and the end product, found what I liked and didn't, and we iterated until we had something better than either of us first imagined.

**What we caught.** A human owner role bypasses Postgres row-level security, so the RLS tests now run as a service principal, which is how the app connects. Our own groundedness checker scored 6 of 25 explanations grounded when all 25 were. Two Genie "misses" were errors in our answer key. Each is a dated note in BUILD_LOG.md and DECISIONS.md, with the original results kept.

**What I learned.** I used this to go past the bar and learn tooling I hadn't used, like routing an app's chat across Genie Agents. As builds get more complex and the product knowledge deeper, planning matters far more to a good build at this level of detail.
