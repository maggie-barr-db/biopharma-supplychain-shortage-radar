-- P06 Lakebase (Postgres) setup for the mitigation workflow. Idempotent.
-- Synced (read-only, from UC): ops.disruption_impact <- silver.impact_base, ops.user_entitlement <- governance.user_entitlement
-- Native (read-write, owned here): ops.mitigation_action, ops.audit_log
-- UC row filters and masks do not reach Lakebase, so the same entitlement rules are enforced here with
-- Postgres RLS. The app connects as its service principal and sets app.user to the signed-in (OBO) user.

CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.mitigation_action (
  action_id BIGSERIAL PRIMARY KEY,
  disruption_id TEXT NOT NULL,
  sku_id TEXT,
  region TEXT NOT NULL,
  action_type TEXT NOT NULL CHECK (action_type IN ('REALLOCATE_INVENTORY', 'EXPEDITE_ALTERNATE_SOURCE',
    'QUALIFY_ALTERNATE_SOURCE', 'ALLOCATE_DEMAND', 'FDA_506C_NOTIFICATION')),
  description TEXT NOT NULL,
  est_revenue_protected NUMERIC,
  proposed_by TEXT NOT NULL,
  proposed_source TEXT NOT NULL CHECK (proposed_source IN ('PLANNER', 'AGENT')),
  on_behalf_of TEXT,
  proposed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED', 'APPROVED', 'REJECTED')),
  decided_by TEXT,
  decided_at TIMESTAMPTZ,
  decision_rationale TEXT);

CREATE TABLE IF NOT EXISTS ops.audit_log (
  audit_id BIGSERIAL PRIMARY KEY,
  action_id BIGINT NOT NULL,
  event TEXT NOT NULL,
  actor TEXT,
  at TIMESTAMPTZ NOT NULL DEFAULT now(),
  details JSONB NOT NULL);

-- Approval rules (Part 11 style): named, entitled approver; no self-approval; rationale required.
CREATE OR REPLACE FUNCTION ops.fn_check_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE who TEXT := current_setting('app.user', true);
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
    IF OLD.status <> 'PROPOSED' THEN RAISE EXCEPTION 'decision already recorded for action %', OLD.action_id; END IF;
    IF NOT EXISTS (SELECT 1 FROM ops.user_entitlement e WHERE e.principal = who AND e.can_approve) THEN
      RAISE EXCEPTION '% is not entitled to approve mitigations', who; END IF;
    IF who = NEW.proposed_by OR who = NEW.on_behalf_of THEN
      RAISE EXCEPTION 'segregation of duties: % cannot decide an action they proposed', who; END IF;
    IF coalesce(trim(NEW.decision_rationale), '') = '' THEN RAISE EXCEPTION 'decision rationale is required'; END IF;
    NEW.decided_by := who;
    NEW.decided_at := now();
  END IF;
  RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION ops.fn_audit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO ops.audit_log (action_id, event, actor, details)
  VALUES (NEW.action_id, TG_OP || ':' || NEW.status, current_setting('app.user', true), to_jsonb(NEW));
  RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION ops.fn_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'audit_log is append-only'; END $$;

DROP TRIGGER IF EXISTS trg_check_decision ON ops.mitigation_action;
CREATE TRIGGER trg_check_decision BEFORE UPDATE ON ops.mitigation_action FOR EACH ROW EXECUTE FUNCTION ops.fn_check_decision();
DROP TRIGGER IF EXISTS trg_audit ON ops.mitigation_action;
CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE ON ops.mitigation_action FOR EACH ROW EXECUTE FUNCTION ops.fn_audit();
DROP TRIGGER IF EXISTS trg_audit_immutable ON ops.audit_log;
CREATE TRIGGER trg_audit_immutable BEFORE UPDATE OR DELETE ON ops.audit_log FOR EACH ROW EXECUTE FUNCTION ops.fn_audit_immutable();

-- Region RLS on the workflow table, mirroring governance.region_filter in UC. FORCE so the owner is filtered too.
ALTER TABLE ops.mitigation_action ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops.mitigation_action FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS region_access ON ops.mitigation_action;
CREATE POLICY region_access ON ops.mitigation_action
  USING (EXISTS (SELECT 1 FROM ops.user_entitlement e WHERE e.principal = current_setting('app.user', true)
                 AND (e.region = '*' OR e.region = mitigation_action.region)))
  WITH CHECK (EXISTS (SELECT 1 FROM ops.user_entitlement e WHERE e.principal = current_setting('app.user', true)
                 AND (e.region = '*' OR e.region = mitigation_action.region)));

-- Read path for the app: region filter and commercial mask over the synced impact table.
CREATE OR REPLACE VIEW ops.v_disruption_impact WITH (security_barrier = true) AS
SELECT d.disruption_id, d.vendor_id, d.event_type, d.event_date, d.sku_id, d.drug, d.region, d.site_id, d.api_id,
       d.single_source, d.weekly_units, d.cover_days_before, d.cover_days_without_vendor, d.requalification_days,
       d.projected_stockout_date, d.supply_gap_days,
       CASE WHEN e.can_see_commercial THEN d.revenue_at_risk END AS revenue_at_risk,
       CASE WHEN e.can_see_commercial THEN d.annual_revenue END AS annual_revenue
FROM ops.disruption_impact d
JOIN ops.user_entitlement e ON e.principal = current_setting('app.user', true) AND (e.region = '*' OR e.region = d.region);
