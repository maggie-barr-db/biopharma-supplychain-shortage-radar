-- P02 business calculations (unfiltered, internal). gold.sql publishes them with row filters and masks;
-- Lakebase syncs silver.impact_base and enforces region access with Postgres RLS (UC policies do not reach it).
-- Reads the late-PO model scores in ml.po_risk_score, so the model changes the cover numbers.
-- As-of date = latest inventory snapshot (synthetic data is dated 2026-11-20).

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.exposure_base
COMMENT "Ontology edges: one row per API x SKU x region, with sourcing, demand and annual revenue"
AS WITH asof AS (SELECT max(snapshot_date) AS d FROM ${catalog}.silver.inventory),
vendors AS (SELECT material_id, count(*) AS vendor_count, array_sort(collect_list(vendor_id)) AS vendor_ids
  FROM ${catalog}.silver.source_list GROUP BY material_id),
demand AS (SELECT f.sku_id, avg(f.forecast_units) AS weekly_units FROM ${catalog}.silver.forecast f, asof
  WHERE f.week_start BETWEEN asof.d AND date_add(asof.d, 91) GROUP BY f.sku_id)
SELECT b.material_id AS api_id, m.material_name AS api_name, s.sku_id, s.drug, s.strength, s.pack, s.region,
  s.site_id, s.net_price, v.vendor_count, v.vendor_count = 1 AS single_source, v.vendor_ids, b.qty_kg_per_unit,
  coalesce(d.weekly_units, 0) AS weekly_units, round(coalesce(d.weekly_units, 0) * 52 * s.net_price, 0) AS annual_revenue
FROM ${catalog}.silver.bom b
JOIN ${catalog}.silver.material m ON b.material_id = m.material_id AND m.material_type = 'API'
JOIN ${catalog}.silver.sku s ON b.sku_id = s.sku_id
JOIN vendors v ON b.material_id = v.material_id
LEFT JOIN demand d ON s.sku_id = d.sku_id;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.cover_base
COMMENT "One row per SKU x region: finished-goods cover plus API cover at the site, with inbound POs discounted by predicted late risk"
AS WITH asof AS (SELECT max(snapshot_date) AS d FROM ${catalog}.silver.inventory),
inv AS (SELECT i.item_id, i.site_id, i.on_hand FROM ${catalog}.silver.inventory i, asof WHERE i.snapshot_date = asof.d),
usage AS (SELECT api_id, site_id, sum(weekly_units * qty_kg_per_unit) / 7 AS api_kg_per_day
  FROM ${catalog}.silver.exposure_base GROUP BY api_id, site_id),
inbound AS (SELECT p.material_id, p.site_id, sum(p.order_qty_kg * (1 - coalesce(r.p_late, 0.3))) AS expected_kg_30d
  FROM ${catalog}.silver.po_line p CROSS JOIN asof
  LEFT JOIN ${catalog}.ml.po_risk_score r ON p.po_number = r.po_number AND p.po_line = r.po_line
  WHERE p.receipt_date IS NULL AND p.promised_date <= date_add(asof.d, 30) GROUP BY p.material_id, p.site_id)
SELECT e.sku_id, e.drug, e.region, e.site_id, e.api_id, e.single_source, e.weekly_units, e.annual_revenue,
  coalesce(si.on_hand, 0) AS sku_on_hand, coalesce(ai.on_hand, 0) AS api_on_hand_kg, coalesce(ib.expected_kg_30d, 0) AS expected_inbound_kg,
  round(coalesce(si.on_hand, 0) / nullif(e.weekly_units / 7, 0), 1) AS sku_cover_days,
  round((coalesce(ai.on_hand, 0) + coalesce(ib.expected_kg_30d, 0)) / nullif(u.api_kg_per_day, 0), 1) AS api_cover_days,
  round(coalesce(si.on_hand, 0) / nullif(e.weekly_units / 7, 0)
    + (coalesce(ai.on_hand, 0) + coalesce(ib.expected_kg_30d, 0)) / nullif(u.api_kg_per_day, 0), 1) AS total_cover_days
FROM ${catalog}.silver.exposure_base e
LEFT JOIN inv si ON si.item_id = e.sku_id AND si.site_id = e.site_id
LEFT JOIN inv ai ON ai.item_id = e.api_id AND ai.site_id = e.site_id
LEFT JOIN usage u ON u.api_id = e.api_id AND u.site_id = e.site_id
LEFT JOIN inbound ib ON ib.material_id = e.api_id AND ib.site_id = e.site_id;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.supplier_risk
COMMENT "One row per vendor: 12-month on-time rate, latest open critical quality event, predicted late risk on open POs"
AS WITH asof AS (SELECT max(snapshot_date) AS d FROM ${catalog}.silver.inventory),
otd AS (SELECT p.vendor_id, round(1 - avg(CAST(p.is_late AS INT)), 3) AS on_time_rate_12m
  FROM ${catalog}.silver.po_line p, asof WHERE p.receipt_date > date_sub(asof.d, 365) GROUP BY p.vendor_id),
ev AS (SELECT vendor_id, max_by(event_type, event_date) AS open_event_type, max(event_date) AS open_event_date
  FROM ${catalog}.silver.supplier_event
  WHERE status = 'OPEN' AND event_type IN ('WARNING_LETTER', 'IMPORT_ALERT', 'FDA_483') GROUP BY vendor_id),
risk AS (SELECT vendor_id, round(avg(p_late), 3) AS mean_p_late_open_po, count(*) AS open_po_lines FROM ${catalog}.ml.po_risk_score GROUP BY vendor_id),
ss AS (SELECT explode(vendor_ids) AS vendor_id, api_id FROM ${catalog}.silver.exposure_base WHERE single_source)
SELECT v.vendor_id, v.vendor_name, v.country, o.on_time_rate_12m, e.open_event_type, e.open_event_date,
  r.mean_p_late_open_po, coalesce(r.open_po_lines, 0) AS open_po_lines,
  (SELECT count(DISTINCT api_id) FROM ss WHERE ss.vendor_id = v.vendor_id) AS single_source_api_count
FROM ${catalog}.silver.vendor v
LEFT JOIN otd o ON v.vendor_id = o.vendor_id
LEFT JOIN ev e ON v.vendor_id = e.vendor_id
LEFT JOIN risk r ON v.vendor_id = r.vendor_id;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.impact_base
COMMENT "One row per active disruption x SKU x region: cover without the disrupted vendor, stockout date, revenue at risk"
AS WITH asof AS (SELECT max(snapshot_date) AS d FROM ${catalog}.silver.inventory),
active AS (SELECT e.vendor_id, e.event_type, max(e.event_date) AS event_date FROM ${catalog}.silver.supplier_event e, asof
  WHERE e.status = 'OPEN' AND e.event_type IN ('WARNING_LETTER', 'IMPORT_ALERT') AND e.event_date >= date_sub(asof.d, 30)
  GROUP BY e.vendor_id, e.event_type),
lost AS (SELECT p.material_id, p.site_id, p.vendor_id, sum(p.order_qty_kg * (1 - coalesce(r.p_late, 0.3))) AS kg
  FROM ${catalog}.silver.po_line p CROSS JOIN asof
  LEFT JOIN ${catalog}.ml.po_risk_score r ON p.po_number = r.po_number AND p.po_line = r.po_line
  WHERE p.receipt_date IS NULL AND p.promised_date <= date_add(asof.d, 30) GROUP BY p.material_id, p.site_id, p.vendor_id),
impact AS (SELECT a.vendor_id, a.event_type, a.event_date, c.*, x.net_price,
  greatest(0, coalesce(c.sku_cover_days, 0) + coalesce(c.api_cover_days, 0)
    * greatest(0, c.api_on_hand_kg + c.expected_inbound_kg - coalesce(l.kg, 0)) / nullif(c.api_on_hand_kg + c.expected_inbound_kg, 0)) AS cover_wo,
  CASE WHEN c.single_source THEN 180 ELSE 30 END AS requalification_days
  FROM active a
  JOIN ${catalog}.silver.exposure_base x ON array_contains(x.vendor_ids, a.vendor_id)
  JOIN ${catalog}.silver.cover_base c ON c.sku_id = x.sku_id AND c.api_id = x.api_id
  LEFT JOIN lost l ON l.material_id = x.api_id AND l.site_id = x.site_id AND l.vendor_id = a.vendor_id)
SELECT concat(i.vendor_id, '-', i.event_date) AS disruption_id, i.vendor_id, i.event_type, i.event_date,
  i.sku_id, i.drug, i.region, i.site_id, i.api_id, i.single_source, i.weekly_units, i.annual_revenue, i.net_price,
  i.total_cover_days AS cover_days_before, round(i.cover_wo, 1) AS cover_days_without_vendor, i.requalification_days,
  date_add(asof.d, CAST(i.cover_wo AS INT)) AS projected_stockout_date,
  round(greatest(0, i.requalification_days - i.cover_wo), 1) AS supply_gap_days,
  round(greatest(0, i.requalification_days - i.cover_wo) * i.weekly_units / 7 * i.net_price, 0) AS revenue_at_risk
FROM impact i CROSS JOIN asof;
