-- Northwind Pipeline Intelligence app state (Lakebase database `northwind`). Idempotent.
-- The Leader tab saves what-if scenarios here; the Funnel tab flags stalled deals for follow-up.

CREATE TABLE IF NOT EXISTS saved_scenarios (
  scenario_id   BIGSERIAL PRIMARY KEY,
  label         TEXT NOT NULL,
  driver        TEXT NOT NULL DEFAULT 'ERP integration gap',
  deals         INT,
  base_volume   NUMERIC,          -- projected annual volume at risk from the driver
  recovery_pct  INT NOT NULL,     -- share of that volume won back in the scenario
  recovered     NUMERIC,          -- base_volume * recovery_pct / 100
  note          TEXT,
  saved_by      TEXT NOT NULL,
  saved_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE saved_scenarios IS 'What-if scenarios saved from the Northwind Pipeline Intelligence Leader tab.';

CREATE TABLE IF NOT EXISTS deal_followups (
  followup_id    BIGSERIAL PRIMARY KEY,
  opportunity_id TEXT NOT NULL,
  account_name   TEXT,
  stage          TEXT,
  days_in_stage  INT,
  status         TEXT NOT NULL DEFAULT 'Flagged' CHECK (status IN ('Flagged','In progress','Resolved')),
  note           TEXT,
  owner          TEXT,
  flagged_by     TEXT NOT NULL,
  flagged_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE deal_followups IS 'Stalled deals flagged for follow-up from the Northwind Pipeline Intelligence Funnel tab.';

-- App service principal access (role created by the app's `postgres` resource binding)
GRANT USAGE ON SCHEMA public TO :"app_sp";
GRANT SELECT, INSERT, UPDATE ON saved_scenarios, deal_followups TO :"app_sp";
GRANT USAGE ON SEQUENCE saved_scenarios_scenario_id_seq, deal_followups_followup_id_seq TO :"app_sp";
