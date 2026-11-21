# BioChain Industries - API Shortage Radar

## 1. See the shortage 52 days out, not 5 days late

When an API supplier gets an FDA Warning Letter, BioChain's planners know within minutes which products, markets and dates are at risk, and every mitigation is approved and audited in one place.

- Impact assessment: **3-5 days today, under an hour with the radar**
- **$7.8M a year** in protected revenue and avoided expedite cost (estimate, assumptions on slide 6)
- For: **VP Supply Chain** (executive sponsor) and **Supply Planning Lead** (domain owner)

Speaker notes: [YOUR WORDS]

## 2. What happened last time

"Last year one of our API suppliers got an FDA Warning Letter. It took almost a week of ERP extracts and spreadsheets to see which products were exposed. Two were already heading for a stockout; we were out for about 45 days." [ASSUMPTION - fictional customer]

- **$18M** lost revenue, **$1.5M** air freight and spot buys
- 8 planners rebuilt the API-to-product map by hand
- Decisions lived in email; nobody could show who approved what

## 3. Why now

- **Shortages are not going away:** ASHP counted **225 active US drug shortages** at the end of Q3 2026 (ASHP National Drug Shortages report).
- **The law now reaches APIs:** FD&C Act 506C requires notifying FDA at least **six months before** an interruption likely to disrupt supply, and the CARES Act extended it to APIs; the application holder owns the notice even when a contract supplier makes the API (21 U.S.C. 356c; FDA draft guidance, Feb 2024).
- **Risk plans are inspectable:** 506C(j) requires a redundancy risk management plan for each establishment making the drug or its API.
- **BioChain's exposure:** **43% of $1.87B revenue** depends on single-source APIs.

## 4. Today vs with the radar

| Today | With the radar |
|---|---|
| Disruption news by email; impact in 3-5 days | New supplier quality signal lands; impact view in minutes |
| Days of cover rebuilt by each planner | One governed definition of days of cover, the same everywhere |
| Late API deliveries are a surprise | A model flags at-risk purchase orders and adjusts cover |
| Mitigations agreed in email | Proposed, approved and time-stamped with an audit trail |

## 5. Live example: Larchmont Synthesis warning letter

| | |
|---|---|
| SKUs exposed | **29** (25 single-source: morphine, midazolam and others) |
| First projected stockout | **2027-01-11** (52 days) - morphine, EU |
| SKUs that run out before an alternate source is qualified | **21** of 29 (180 days to qualify) |
| Revenue at risk | **$30.0M** of $187M annual revenue exposed |
| Time from signal to this view | one pipeline run (minutes) |

Demo: Radar -> Impact -> propose -> approve -> Ask. [YOUR WORDS for the talk track]

## 6. Value, with assumptions

| Value driver | Baseline | Change | Assumption | Value / yr |
|---|---|---|---|---|
| Revenue lost to API stockouts | $18M | 40% fewer stockout days | 3-4 extra days to reallocate stock and pull forward alternate supply | **$7.2M** |
| Expedite and spot-buy premium | $1.5M | 30% lower | Earlier action allows standard freight and negotiated buys | **$0.45M** |
| Planner effort | 192 planner-days | ~95% lower | Under an hour per event; $150K loaded FTE | **$0.13M** |
| Audit and regulatory exposure | Email decisions | 100% recorded | Risk reduction | not monetised |
| **Total** | | | | **~$7.8M** |

- **VP Supply Chain watches:** revenue at risk, stockout days, single-source exposure.
- **Supply Planning Lead watches:** time to impact, days of cover, time to an approved decision.

## 7. How it works

- **Ingest** ERP, supplier quality and forecast files, and match supplier codes across systems.
- **Govern** one published layer: each region sees its own sites, price and revenue only for those entitled.
- **Predict** which API purchase orders will be late (beats the simple vendor-history baseline: PR-AUC 0.56 vs 0.46).
- **Explain and route** questions to the right agent: supplier quality or supply exposure.
- **Act** in an operational store: AI proposes, people approve, everything is audited.
- **One app** for planners and executives, running as the signed-in user.

## 8. Why you can trust it

- **AI proposes, people decide:** the agent can only create a PROPOSED action; an entitled approver must sign off with a rationale, and nobody approves their own proposal.
- **Audit trail:** every proposal and decision is time-stamped and append-only (21 CFR Part 11 style).
- **Least privilege:** an EU planner sees EU SKUs and no revenue, in the app, in Genie and in the operational store.
- **Measured, not assumed:** the late-PO model had to beat a baseline on held-out data before we used it; benchmark questions grade the agents.

## 9. Path to production (90 days)

- **Days 0-30:** connect SAP and the supplier quality system with Lakeflow Connect; load real BOM and source lists for the top 20 single-source APIs.
- **Days 30-60:** move entitlements to ABAC with governed tags; CI/CD for the bundle; planners use the radar in weekly S&OP.
- **Days 60-90:** add alternate-source qualification tracking and 506C notification workflow; measure time to impact on the next real event.

## 10. The ask

- **Pilot** on the top 20 single-source APIs with one regional planning team.
- **Success:** next disruption assessed in under an hour; every mitigation approved in the radar; one avoided stockout.
- **Next step:** 60-minute working session with the Supply Planning Lead to confirm data sources and benchmark questions. [YOUR WORDS]
