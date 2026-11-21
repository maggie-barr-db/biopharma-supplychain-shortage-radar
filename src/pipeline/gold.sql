-- P02/P03 gold: the published, governed layer. Planners, Genie and the app read only these tables.
-- Row filter: governance.region_filter on region. Masks: governance.mask_commercial on price and revenue.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.api_exposure (
  api_id STRING COMMENT 'Active pharmaceutical ingredient material id', api_name STRING, sku_id STRING, drug STRING,
  strength STRING, pack STRING, region STRING COMMENT 'Market: US, EU or APAC', site_id STRING,
  net_price DOUBLE MASK ${catalog}.governance.mask_commercial COMMENT 'Net price per unit (commercial, masked)',
  vendor_count BIGINT COMMENT 'Approved vendors for the API', single_source BOOLEAN COMMENT 'True when only one approved vendor',
  vendor_ids ARRAY<STRING>, qty_kg_per_unit DOUBLE, weekly_units DOUBLE COMMENT 'Average forecast units per week, next 13 weeks',
  annual_revenue DOUBLE MASK ${catalog}.governance.mask_commercial COMMENT 'Annualised revenue (commercial, masked)')
WITH ROW FILTER ${catalog}.governance.region_filter ON (region)
COMMENT "Ontology edges: one row per API x SKU x region with sourcing, demand and revenue"
AS SELECT * FROM ${catalog}.silver.exposure_base;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.days_of_cover (
  sku_id STRING, drug STRING, region STRING, site_id STRING, api_id STRING, single_source BOOLEAN, weekly_units DOUBLE,
  annual_revenue DOUBLE MASK ${catalog}.governance.mask_commercial, sku_on_hand DOUBLE, api_on_hand_kg DOUBLE,
  expected_inbound_kg DOUBLE COMMENT 'Open PO kg due in 30 days, discounted by predicted late risk',
  sku_cover_days DOUBLE, api_cover_days DOUBLE, total_cover_days DOUBLE COMMENT 'Finished-goods cover plus API cover, in days')
WITH ROW FILTER ${catalog}.governance.region_filter ON (region)
COMMENT "One row per SKU x region: days of cover including risk-adjusted inbound API"
AS SELECT * FROM ${catalog}.silver.cover_base;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.disruption_impact (
  disruption_id STRING, vendor_id STRING, event_type STRING, event_date DATE, sku_id STRING, drug STRING, region STRING,
  site_id STRING, api_id STRING, single_source BOOLEAN, weekly_units DOUBLE,
  annual_revenue DOUBLE MASK ${catalog}.governance.mask_commercial, net_price DOUBLE MASK ${catalog}.governance.mask_commercial,
  cover_days_before DOUBLE, cover_days_without_vendor DOUBLE COMMENT 'Days of cover if the disrupted vendor ships nothing',
  requalification_days INT COMMENT 'Assumed days to qualify an alternate source (180 single-source, 30 otherwise)',
  projected_stockout_date DATE, supply_gap_days DOUBLE COMMENT 'Days without supply before an alternate source is ready',
  revenue_at_risk DOUBLE MASK ${catalog}.governance.mask_commercial COMMENT 'Supply gap days x daily revenue (commercial, masked)')
WITH ROW FILTER ${catalog}.governance.region_filter ON (region)
COMMENT "One row per active disruption x SKU x region: cover without the vendor, stockout date, revenue at risk"
AS SELECT * FROM ${catalog}.silver.impact_base;
