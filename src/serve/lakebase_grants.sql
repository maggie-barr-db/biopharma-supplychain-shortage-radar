-- P06 grants for an app or agent service principal role (role created by the app's postgres resource
-- or `databricks postgres create-role`). Run once per principal with tools/pg.py; ${role} is its client id.
GRANT USAGE ON SCHEMA ops TO "${role}";
GRANT SELECT, INSERT, UPDATE ON ops.mitigation_action TO "${role}";
GRANT USAGE, SELECT ON SEQUENCE ops.mitigation_action_action_id_seq TO "${role}";
GRANT SELECT, INSERT ON ops.audit_log TO "${role}";
GRANT USAGE, SELECT ON SEQUENCE ops.audit_log_audit_id_seq TO "${role}";
GRANT SELECT ON ops.user_entitlement, ops.disruption_impact, ops.v_disruption_impact TO "${role}";
