-- P02 bronze: raw files as landed, plus source file and load time. Auto Loader via read_files.
-- Schema contract: schemaEvolutionMode 'rescue' keeps the agreed columns and puts any unexpected or mistyped
-- field in _rescued_data instead of silently adding columns; the expectation counts those rows (warn and track).
-- A schema change that blanks a key column then fails the update in silver (po_key, vendor_key).
-- ${catalog} and ${landing} come from the pipeline configuration (resources/pipeline.yml).

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.vendor (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "ERP vendor master as landed"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/erp/vendors/', format => 'csv', schemaEvolutionMode => 'rescue', header => true, schemaHints => 'duns STRING');

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.material (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "ERP material master as landed"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/erp/materials/', format => 'csv', schemaEvolutionMode => 'rescue', header => true);

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.source_list (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "ERP approved vendors per material as landed"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/erp/source_list/', format => 'csv', schemaEvolutionMode => 'rescue', header => true);

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.bom (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "ERP bill of materials as landed"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/erp/bom/', format => 'csv', schemaEvolutionMode => 'rescue', header => true);

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.po_line (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "ERP purchase order lines as landed, including re-sent files"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/erp/po_lines/', format => 'csv', schemaEvolutionMode => 'rescue', header => true,
  schemaHints => 'po_number STRING, order_qty DOUBLE, lead_time_days INT, order_date DATE, promised_date DATE, receipt_date DATE');

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.inventory (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "ERP daily inventory snapshots as landed"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/erp/inventory/', format => 'csv', schemaEvolutionMode => 'rescue', header => true,
  schemaHints => 'snapshot_date DATE, on_hand DOUBLE');

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.supplier_event (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "Supplier quality system events as landed (own supplier codes)"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/supplier_quality/', format => 'json', schemaEvolutionMode => 'rescue',
  schemaHints => 'dunsNumber STRING, eventDate DATE');

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.forecast (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "Demand planning forecast files as landed, including late and duplicate deliveries"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/forecast/', format => 'csv', schemaEvolutionMode => 'rescue', header => true,
  schemaHints => 'published_at DATE, week_start DATE, forecast_units INT');

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.sku (CONSTRAINT schema_contract EXPECT (_rescued_data IS NULL)) COMMENT "Commercial SKU master as landed"
AS SELECT *, _metadata.file_path AS _source_file, current_timestamp() AS _load_ts
FROM STREAM read_files('${landing}/sku/', format => 'csv', schemaEvolutionMode => 'rescue', header => true, schemaHints => 'net_price DOUBLE');
