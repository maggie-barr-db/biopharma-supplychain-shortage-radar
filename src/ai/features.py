"""Point-in-time features for the late-PO model, shared by training and scoring.

Timing rule (EVAL_PROTOCOL.md): every feature uses only information known at PO creation.
Vendor history counts only receipts before the order date; quality events only before the order date.
Event status is not used because it reflects today, not the order date.
"""

FEATURES_NUM = ["vendor_on_time_rate_365d", "vendor_receipts_365d", "critical_events_180d",
                "critical_events_30d", "lead_time_days", "order_qty_kg", "order_month"]
FEATURES_CAT = ["vendor_country", "site_region", "material_type"]


def feature_sql(catalog: str, where: str) -> str:
    """SQL returning one row per PO line in silver.po_line matching `where`, with features and label."""
    return f"""
    WITH po AS (SELECT * FROM {catalog}.silver.po_line WHERE {where}),
    hist AS (
      SELECT p.po_number, p.po_line, count(h.po_number) AS vendor_receipts_365d,
             avg(CASE WHEN h.is_late THEN 0.0 ELSE 1.0 END) AS vendor_on_time_rate_365d
      FROM po p LEFT JOIN {catalog}.silver.po_line h
        ON h.vendor_id = p.vendor_id AND h.receipt_date < p.order_date
       AND h.receipt_date >= date_sub(p.order_date, 365)
      GROUP BY p.po_number, p.po_line),
    q AS (
      SELECT p.po_number, p.po_line,
             count_if(e.event_type IN ('FDA_483', 'WARNING_LETTER', 'IMPORT_ALERT')
                      AND e.event_date >= date_sub(p.order_date, 180)) AS critical_events_180d,
             count_if(e.event_type IN ('WARNING_LETTER', 'IMPORT_ALERT')
                      AND e.event_date >= date_sub(p.order_date, 30)) AS critical_events_30d
      FROM po p LEFT JOIN {catalog}.silver.supplier_event e
        ON e.vendor_id = p.vendor_id AND e.event_date < p.order_date
      GROUP BY p.po_number, p.po_line)
    SELECT p.po_number, p.po_line, p.vendor_id, p.material_id, p.order_date, p.promised_date, p.is_late,
           coalesce(h.vendor_on_time_rate_365d, 0.7) AS vendor_on_time_rate_365d,
           coalesce(h.vendor_receipts_365d, 0) AS vendor_receipts_365d,
           coalesce(q.critical_events_180d, 0) AS critical_events_180d,
           coalesce(q.critical_events_30d, 0) AS critical_events_30d,
           CAST(p.lead_time_days AS DOUBLE) AS lead_time_days, p.order_qty_kg, month(p.order_date) AS order_month,
           v.country AS vendor_country, left(p.site_id, 2) AS site_region, m.material_type
    FROM po p
    JOIN hist h USING (po_number, po_line)
    JOIN q USING (po_number, po_line)
    JOIN {catalog}.silver.vendor v ON v.vendor_id = p.vendor_id
    JOIN {catalog}.silver.material m ON m.material_id = p.material_id
    """
