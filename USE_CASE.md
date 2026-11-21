# USE_CASE.md - BioChain Industries: API shortage radar

All company facts and numbers below are fictional assumptions for a synthetic customer, marked [ASSUMPTION]. Public facts carry a source.

## 1. One-line outcome [YOUR WORDS]

When a single-source API supplier is disrupted, BioChain's planners see the exposed products, lots, markets and revenue in under an hour instead of 3-5 business days, and every mitigation decision is approved and auditable, protecting an estimated $7.8M a year in revenue and expedite cost.

## 2. The problem in the customer's words [YOUR WORDS]

"Last year one of our API suppliers got an FDA Warning Letter. It took us almost a week of ERP extracts and spreadsheets to work out which products were exposed, and by then two of them were already heading for a stockout. We were out for about 45 days. That cost us roughly $18M in lost revenue and another $1.5M in air freight and spot buys." [ASSUMPTION]

## 3. Why now

- **Shortages stay high.** ASHP counted 225 active US drug shortages at the end of Q3 2026 (223 in Q1, 227 in Q2). Source: ASHP National Drug Shortages report, Jan 2001-Sep 2026 (ashp.org).
- **The law now reaches APIs.** FD&C Act section 506C requires notifying FDA at least six months before a manufacturing interruption likely to cause a meaningful supply disruption, or as soon as practicable, and the CARES Act extended this to API interruptions. The application holder owns that notice even when a third-party supplier makes the API. Source: 21 U.S.C. 356c; FDA draft guidance, Feb 2024.
- **Regulators expect proactive risk plans.** Section 506C(j) requires a redundancy risk management plan covering each establishment that makes the drug or its API, and FDA can inspect it. Source: 21 U.S.C. 356c(j); FDA draft guidance, May 2022.
- **Peers are building supply chain control towers** for multi-tier visibility. [CHECK: find a citable industry source or drop]

## 4. Personas

| | VP Supply Chain (executive sponsor) | Supply Planning Lead (domain owner) |
|---|---|---|
| Reports upward | Quarterly supply continuity and revenue at risk to the executive committee; owns the supply risk line on the board risk register [ASSUMPTION] | Weekly days-of-cover and exception list into S&OP [ASSUMPTION] |
| Works today | Hears about disruptions late, by email, with numbers that differ by who built the spreadsheet | Team of 8 planners rebuilds the API-to-SKU-to-market map by hand for every event [ASSUMPTION] |
| KPIs owned | Revenue at risk, stockout days, OTIF, mitigation cost, single-source exposure | Time to impact assessment, time to mitigation decision, days of cover, predicted late POs, second-source readiness |

## 5. Today versus tomorrow

| Today | Tomorrow |
|---|---|
| Disruption news arrives by email; impact takes 3-5 days of spreadsheets | Supplier signal lands, pipeline refreshes, impact view shows affected SKUs, lots, markets and revenue in under an hour |
| Days of cover recomputed manually, per planner, inconsistently | One governed definition of days of cover (metric view), the same in the app, Genie and the deck |
| Mitigation agreed in email threads, no record of who approved what | Mitigation proposed, approved and time-stamped in an auditable workflow (Part 11 style) |
| Late API deliveries are a surprise | A model flags at-risk purchase orders weeks ahead, feeding projected days of cover |

## 6. Value hypothesis [YOUR WORDS for the framing; numbers are assumptions]

| Value driver | Current baseline | Expected change | Assumption | Illustrative value / yr |
|---|---|---|---|---|
| Lost revenue from API-driven stockouts | $18M (one major event / yr, 45 stockout days on 2 products) | 40% fewer stockout days | Earlier impact view buys 3-4 days to reallocate inventory and pull forward alternate supply | $7.2M |
| Expedite and spot-buy premium | $1.5M | 30% lower | Earlier action allows sea or standard freight and negotiated buys | $0.45M |
| Planner effort on impact assessment | 8 planners x 4 days x 6 events = 192 planner-days | ~95% lower | Assessment drops to under an hour; $150K loaded cost per FTE (~220 days) | ~$0.13M |
| Regulatory and audit exposure | Decisions in email; 506C timing tracked manually | 100% decisions with approver, timestamp, rationale | Risk reduction, not monetised | Not monetised |
| **Total** | | | | **~$7.8M** |

## 7. The data (synthetic, generated in-pipeline)

| Source system | Tables (approx rows) | What is messy |
|---|---|---|
| ERP (SAP-style) | materials (~500), vendors (60), bill of materials (~1,200 lines), purchase order lines (~24,000 / yr), inventory snapshots by site (~170,000 / yr) | Re-sent PO files create duplicate lines; units mix kg and g; missing lead times on older vendors |
| Supplier quality system | supplier quality events: inspections, FDA 483 observations, Warning Letters, audit findings (~400) | Supplier codes do not match ERP vendor IDs; free-text findings; different field names for the same supplier |
| Demand planning tool | weekly demand forecast files by SKU and market (~350 SKUs x 3 markets x 26 weeks) | Files arrive late or twice; occasional negative forecasts |
| Commercial | SKU master with net price and market (~350) | Discontinued SKUs still present |

Network: 40 finished drugs, ~350 SKUs, ~120 APIs and key excipients, 60 suppliers, about 35% of APIs single-sourced, 6 sites, 3 regions (US, EU, APAC). [ASSUMPTION]

## 8. How the six stages serve the story (for the Supply Planning Lead)

- **Lakeflow:** lands ERP, supplier quality and forecast files and conforms the supplier codes, so one disruption signal maps to the right vendor.
- **Unity Catalog:** one governed set of tables and lineage; contract cost is masked for planners and each region sees only its own sites.
- **Lakebase:** the live mitigation workflow; planners propose and approvers sign off, with an audit trail.
- **ML or GenAI:** a model predicts which API purchase orders will be late, and an assistant explains impact and drafts the mitigation options.
- **Genie:** planners and the VP ask "which products run out first if supplier X stops?" in plain English over governed metrics.
- **App:** one screen from signal to impact to approved decision, running as the signed-in user.

## 9. What we will NOT build

Real ERP or FDA connectors (synthetic files stand in), tier-2 and deeper suppliers, Delta Sharing with suppliers, a custom agent router, Genie Workbench auto-optimisation, a CI pipeline, and automated FDA 506C submissions (we flag them only).

## 10. Challenge

- **Make the ML step essential:** predicted late POs must feed projected days of cover and the impact view; otherwise it reads as bolted on.
- **Make Lakebase essential:** the app writes decisions there and reads them back; Genie and the deck report on approved mitigations.
- **The Knowledge Assistant is the weakest link:** it is only needed if supplier quality findings are free text worth searching. Keep it if routing between structured and unstructured is the 300-level goal; otherwise cut it.
- **Demo moment:** drop a new "Warning Letter" supplier quality file, let the pipeline run, and watch the impact view and Genie answers change. This proves the stages are connected.
- **Stay specific:** name the drug classes (for example sterile injectables), not "products", in the deck and demo. [YOUR WORDS]
