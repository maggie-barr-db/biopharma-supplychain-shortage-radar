-- P02 silver: cleaned and conformed. DQ policy (DECISIONS.md #3): quarantine duplicate PO lines and
-- negative forecasts, warn on missing lead times and unmatched suppliers, fail on null keys.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.vendor (
  CONSTRAINT vendor_key EXPECT (vendor_id IS NOT NULL) ON VIOLATION FAIL UPDATE)
COMMENT "One row per ERP vendor, with a normalised name for matching"
AS SELECT vendor_id, vendor_name, country, duns, CAST(created_year AS INT) AS created_year,
  regexp_replace(upper(vendor_name), '[^A-Z ]', '') AS name_key
FROM ${catalog}.bronze.vendor;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.supplier_xref
COMMENT "Supplier quality code to ERP vendor_id: DUNS match first, normalised name second"
AS WITH codes AS (
  SELECT DISTINCT supplierCode AS supplier_code, max(dunsNumber) AS duns,
    regexp_replace(replace(upper(supplierName), 'PHARMA INGR.', 'PHARMA INGREDIENTS'), '[^A-Z ]', '') AS name_key
  FROM ${catalog}.bronze.supplier_event GROUP BY supplierCode, supplierName)
SELECT c.supplier_code, coalesce(d.vendor_id, n.vendor_id) AS vendor_id,
  CASE WHEN d.vendor_id IS NOT NULL THEN 'DUNS' WHEN n.vendor_id IS NOT NULL THEN 'NAME' ELSE 'UNMATCHED' END AS match_method
FROM codes c
LEFT JOIN ${catalog}.silver.vendor d ON c.duns = d.duns
LEFT JOIN ${catalog}.silver.vendor n ON d.vendor_id IS NULL AND c.name_key = n.name_key
QUALIFY row_number() OVER (PARTITION BY c.supplier_code ORDER BY CASE WHEN d.vendor_id IS NOT NULL THEN 0 ELSE 1 END) = 1;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.supplier_event (
  CONSTRAINT matched_supplier EXPECT (vendor_id IS NOT NULL))
COMMENT "One row per supplier quality event, mapped to the ERP vendor"
AS SELECT x.vendor_id, e.supplierCode AS supplier_code, e.eventType AS event_type, e.eventDate AS event_date,
  e.severity, e.status, e.findingText AS finding_text, e.siteCountry AS site_country, e._source_file
FROM ${catalog}.bronze.supplier_event e
LEFT JOIN ${catalog}.silver.supplier_xref x ON e.supplierCode = x.supplier_code;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.material COMMENT "One row per material"
AS SELECT DISTINCT material_id, material_name, material_type, base_uom FROM ${catalog}.bronze.material;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.source_list COMMENT "One row per material x approved vendor"
AS SELECT DISTINCT material_id, vendor_id, CAST(lead_time_days AS INT) AS lead_time_days FROM ${catalog}.bronze.source_list;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.bom COMMENT "One row per SKU x component"
AS SELECT DISTINCT sku_id, material_id, CAST(qty_kg_per_unit AS DOUBLE) AS qty_kg_per_unit FROM ${catalog}.bronze.bom;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.sku COMMENT "One row per active SKU (discontinued removed)"
AS SELECT sku_id, drug, strength, pack, region, site_id, net_price FROM ${catalog}.bronze.sku WHERE status = 'ACTIVE';

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.po_line_ranked COMMENT "PO lines with duplicate rank; feeds po_line and po_line_quarantine"
AS SELECT *, row_number() OVER (PARTITION BY po_number, po_line ORDER BY _source_file LIKE '%resend%', _load_ts) AS dup_rank
FROM ${catalog}.bronze.po_line;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.po_line (
  CONSTRAINT po_key EXPECT (po_number IS NOT NULL AND material_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT has_lead_time EXPECT (lead_time_source = 'PO'))
COMMENT "One row per PO line: duplicates removed, grams converted to kg, missing lead time filled from the source list"
AS SELECT p.po_number, CAST(p.po_line AS INT) AS po_line, p.material_id, p.vendor_id, p.site_id,
  CASE WHEN p.uom = 'G' THEN p.order_qty / 1000 ELSE p.order_qty END AS order_qty_kg,
  p.order_date, p.promised_date, p.receipt_date,
  coalesce(p.lead_time_days, s.lead_time_days) AS lead_time_days,
  CASE WHEN p.lead_time_days IS NULL THEN 'SOURCE_LIST' ELSE 'PO' END AS lead_time_source,
  CASE WHEN p.receipt_date IS NULL THEN NULL ELSE datediff(p.receipt_date, p.promised_date) > 7 END AS is_late
FROM ${catalog}.silver.po_line_ranked p
LEFT JOIN ${catalog}.silver.source_list s ON p.material_id = s.material_id AND p.vendor_id = s.vendor_id
WHERE p.dup_rank = 1;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.po_line_quarantine COMMENT "Duplicate PO lines from re-sent files"
AS SELECT po_number, po_line, material_id, vendor_id, _source_file, 'DUPLICATE_RESEND' AS reason
FROM ${catalog}.silver.po_line_ranked WHERE dup_rank > 1;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.inventory COMMENT "One row per item x site x snapshot date"
AS SELECT DISTINCT snapshot_date, site_id, item_id, item_type, on_hand, uom FROM ${catalog}.bronze.inventory;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.forecast_ranked COMMENT "Forecast rows ranked so the latest published file wins"
AS SELECT *, row_number() OVER (PARTITION BY sku_id, week_start ORDER BY published_at DESC, _source_file LIKE '%resend%') AS pub_rank
FROM ${catalog}.bronze.forecast;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.forecast (
  CONSTRAINT non_negative EXPECT (forecast_units >= 0) ON VIOLATION DROP ROW)
COMMENT "One row per SKU x week from the latest published forecast"
AS SELECT sku_id, region, week_start, forecast_units, published_at
FROM ${catalog}.silver.forecast_ranked WHERE pub_rank = 1;

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.forecast_quarantine COMMENT "Negative forecast quantities held for planner review"
AS SELECT sku_id, region, week_start, forecast_units, published_at, _source_file, 'NEGATIVE_FORECAST' AS reason
FROM ${catalog}.silver.forecast_ranked WHERE pub_rank = 1 AND forecast_units < 0;
