# API Shortage Radar for BioChain Industries

**When an API supplier gets an FDA Warning Letter, BioChain's VP Supply Chain sees how much revenue is at risk, which products run out and when, and gets an approved, audited mitigation plan moving in minutes instead of 3-5 days, before patients feel the shortage.** On the demo disruption that is $30.0M of revenue at risk across 29 SKUs, with the first stockout 52 days out. It gives supply chain leadership an operational view of disruptions that will keep happening, and a way to route the mitigation to the right people when they do.

BioChain Industries is a fictional mid-size biopharma manufacturer (synthetic data only): 288 active SKUs across US, EU and APAC, $1.87B revenue, 43% of it dependent on single-source APIs.

## The result on the demo disruption

An FDA Warning Letter lands for supplier V100103 (Larchmont Synthesis). Within one pipeline run:

- **29 SKUs exposed**, 25 single-source (morphine, midazolam and others), across all three regions.
- **First projected stockout 2027-01-11**, 52 days out; 21 SKUs run out before an alternate source can be qualified (180 days assumed).
- **$30.0M revenue at risk** of $187M annual revenue exposed; the VP sees it, planners see units and days only.
- The routing agent answers "which products are exposed to the supplier that just got a warning letter?" by asking the Supplier Quality agent first and the Supply Exposure agent second, then proposes a mitigation that a supply executive must approve.

**About $7.8M a year (estimate for a fictional company)**, from fewer stockout days, lower expedite cost and planner time. The baseline and each assumption, and the real FDA, ASHP, ASPE and Vizient sources behind the problem, are in USE_CASE.md (sections 2 and 6).

## How it works

Synthetic ERP, supplier quality and forecast files land in a UC volume; Lakeflow builds bronze, silver and a governed gold layer; a late-PO model's scores change days of cover; `ai_query` explains each at-risk SKU; Lakebase runs the mitigation workflow and decisions land back in Delta; two Genie Agents and a routing agent answer questions; a React app runs it all as the signed-in user. **VALIDATION.md** maps every stage to its code and evidence; `evidence/` holds the outputs.

## Decisions a technical buyer will ask about

Full list and the evaluation protocol in **DECISIONS.md**.
- **Row filters and masks instead of ABAC** (no governed tags left in the workspace); the design maps onto ABAC. UC policies don't reach Lakebase, so Postgres RLS enforces the same rules there.
- **Routing is a code agent over Genie Agents** (Supervisor Agent and Knowledge Assistant are legacy), graded 15 of 15. The user's identity flows app -> agent -> Genie because the app requests the `apps` scope plus the agent's `genie` scope.
- **AI is measured, not trusted:** the model beat its baseline (PR-AUC 0.562 vs 0.455), Genie answered 11 of 12 benchmark questions, and 25 of 25 explanations were grounded.

## Deploy into a new workspace

```
databricks bundle deploy --profile <p>
databricks bundle run radar_rebuild --profile <p>  # generate, full refresh, train, score, explain, sync
python tools/db.py sql src/governance/policies.sql --profile <p> --warehouse <id> --var catalog=supply_chain ...
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
