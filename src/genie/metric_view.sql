-- P07 metric view: one governed definition of the supply KPIs, used by Genie and the app.
-- Reads gold.days_of_cover, so the caller's region filter and commercial mask still apply.
CREATE OR REPLACE VIEW ${catalog}.gold.mv_supply_kpis
WITH METRICS LANGUAGE YAML
COMMENT 'Governed supply KPIs: days of cover, single-source exposure, revenue (masked for planners)'
AS $$
version: 1.1
source: ${catalog}.gold.days_of_cover
dimensions:
  - name: region
    expr: region
  - name: drug
    expr: drug
  - name: site_id
    expr: site_id
  - name: single_source
    expr: single_source
measures:
  - name: sku_count
    expr: COUNT(DISTINCT sku_id)
  - name: avg_days_of_cover
    expr: AVG(total_cover_days)
  - name: skus_under_60_days_cover
    expr: COUNT(DISTINCT CASE WHEN total_cover_days < 60 THEN sku_id END)
  - name: annual_revenue
    expr: SUM(annual_revenue)
  - name: single_source_revenue
    expr: SUM(CASE WHEN single_source THEN annual_revenue END)
  - name: single_source_revenue_share
    expr: SUM(CASE WHEN single_source THEN annual_revenue END) / SUM(annual_revenue)
$$;
