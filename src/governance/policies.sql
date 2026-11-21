-- P03 governance: entitlement table + row filter and column mask functions (classic UC, no governed tags).
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
