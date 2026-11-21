-- P05 read grants for a planner principal: gold (governed) layer only, never silver or bronze.
GRANT USE CATALOG ON CATALOG ${catalog} TO `${principal}`;
GRANT USE SCHEMA ON SCHEMA ${catalog}.gold TO `${principal}`;
GRANT SELECT ON SCHEMA ${catalog}.gold TO `${principal}`;
GRANT USE SCHEMA ON SCHEMA ${catalog}.governance TO `${principal}`;
GRANT SELECT ON TABLE ${catalog}.governance.user_entitlement TO `${principal}`;
