-- Score table read by gold.days_of_cover and gold.disruption_impact; overwritten by the score_po_risk task.
CREATE TABLE IF NOT EXISTS supply_chain.ml.po_risk_score (
  po_number STRING, po_line INT, vendor_id STRING, material_id STRING,
  p_late DOUBLE COMMENT 'Predicted probability the PO line arrives more than 7 days late',
  baseline_p_late DOUBLE COMMENT 'Baseline: 1 - vendor trailing 12-month on-time rate',
  model_version STRING, scored_at TIMESTAMP)
COMMENT 'Late-PO model scores for open purchase order lines';
