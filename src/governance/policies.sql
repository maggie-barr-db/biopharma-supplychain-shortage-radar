-- P03 Unity Catalog setup: entitlement table, row filter and column mask functions (classic UC, no governed tags),
-- planner read grants, and the model score table the gold layer reads. Run once per workspace with tools/db.py sql.
-- Applied to gold tables in the pipeline definitions (WITH ROW FILTER / MASK). ABAC is the production path.
-- Deny by default: a principal not in the entitlement table sees no rows and no commercial values.

CREATE TABLE IF NOT EXISTS ${catalog}.governance.user_entitlement (
  principal STRING COMMENT 'User email or service principal application id',
  persona STRING COMMENT 'supply_exec | planner_us | planner_eu | planner_apac',
  region STRING COMMENT 'US | EU | APAC | * for all regions',
  can_see_commercial BOOLEAN COMMENT 'May see net price, revenue and revenue at risk',
  can_approve BOOLEAN COMMENT 'May approve mitigation actions in Lakebase')
COMMENT 'Who may see which region and commercial values, read by the filter and mask functions and by the app';

MERGE INTO ${catalog}.governance.user_entitlement t
USING (SELECT * FROM VALUES
  ('${exec_user}', 'supply_exec', '*', true, true),
  ('${planner_eu_sp}', 'planner_eu', 'EU', false, false)
  AS v(principal, persona, region, can_see_commercial, can_approve)) s
ON t.principal = s.principal
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE FUNCTION ${catalog}.governance.region_filter(row_region STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: the caller sees only rows for regions they are entitled to'
RETURN EXISTS (SELECT 1 FROM ${catalog}.governance.user_entitlement e
               WHERE e.principal = current_user() AND (e.region = '*' OR e.region = row_region));

CREATE OR REPLACE FUNCTION ${catalog}.governance.mask_commercial(v DOUBLE)
RETURNS DOUBLE
COMMENT 'Column mask: price and revenue values only for entitled personas, NULL otherwise'
RETURN CASE WHEN EXISTS (SELECT 1 FROM ${catalog}.governance.user_entitlement e
                         WHERE e.principal = current_user() AND e.can_see_commercial) THEN v END;

-- Planner read grants: gold (governed) layer only, never silver or bronze. ${principal} = planner user or SP.
GRANT USE CATALOG ON CATALOG ${catalog} TO `${principal}`;
GRANT USE SCHEMA ON SCHEMA ${catalog}.gold TO `${principal}`;
GRANT SELECT ON SCHEMA ${catalog}.gold TO `${principal}`;
GRANT USE SCHEMA ON SCHEMA ${catalog}.governance TO `${principal}`;
GRANT SELECT ON TABLE ${catalog}.governance.user_entitlement TO `${principal}`;

-- Score table read by gold.days_of_cover and gold.disruption_impact; overwritten by the score_po_risk task.
CREATE TABLE IF NOT EXISTS ${catalog}.ml.po_risk_score (
  po_number STRING, po_line INT, vendor_id STRING, material_id STRING,
  p_late DOUBLE COMMENT 'Predicted probability the PO line arrives more than 7 days late',
  baseline_p_late DOUBLE COMMENT 'Baseline: 1 - vendor trailing 12-month on-time rate',
  model_version STRING, scored_at TIMESTAMP)
COMMENT 'Late-PO model scores for open purchase order lines';
