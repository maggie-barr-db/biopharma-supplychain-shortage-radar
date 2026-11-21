# EVAL_PROTOCOL.md

Written 2026-11-21, before any model, agent or Genie result was produced. Later changes are added as dated notes at the bottom; original results stay in evidence/.

## 1. Late-PO model

- **Question:** will an open API purchase order line arrive more than 7 days after its promised date?
- **Simple baseline:** the vendor's trailing 12-month on-time rate, used as the score.
- **Held-out data:** the most recent 3 months of PO lines by PO creation date. Training uses only earlier PO lines.
- **Timing rule:** every feature uses only information known at PO creation (vendor history up to that date, quality events dated before it, lead time on the PO). No feature may read the actual receipt date or later quality events.
- **Main measure:** PR-AUC on the holdout (late lines are the minority class). Secondary: recall among the top 20% highest-risk lines.
- **No claim:** if the model's PR-AUC beats the baseline by less than 0.05, we report that the model adds no value and the days-of-cover projection uses the baseline instead.

## 2. Genie Agents and routing agent

- **Benchmark:** 15 questions written now, before tuning: 7 for Supply Exposure, 5 for Supplier Quality, 3 that need both agents or the mitigation tool. Each has the expected agent and an expected answer or SQL.
- **Main measures:** answer correctness per question (matches expected result) and routing accuracy (the routing agent called the expected agent or tool).
- **Bar:** at least 12 of 15 correct and at least 13 of 15 routed correctly. Below that, we record the misses and what we changed, and rerun once.
- **Access check:** 3 of the benchmark questions are rerun as the `planner_eu` service principal; answers must exclude US sites and show no cost.

## 3. ai_query explanations

- **Cases:** 10 disruption impacts.
- **Judges (MLflow):** groundedness (every number in the explanation appears in the source row) and relevance to the planner's decision.
- **Bar:** 10 of 10 grounded. Any ungrounded number is a failure, and we tighten the prompt and rerun.

## Change notes

(none yet)
