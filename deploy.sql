-- =============================================================================
-- Northwind Pipeline Intelligence demo : schema + volumes
-- Target: example-workspace, fe_demo_catalog.northwind_pipeline
-- Run order: deploy.sql -> upload files (rebuild.sh) -> pipeline (bundle) -> deploy_metric_views.sql -> deploy_functions.sql -> verify.sql
-- Independent of the broader northwind (commercial-loop) demo schema.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS fe_demo_catalog.northwind_pipeline
COMMENT 'Northwind (Northwind Commercial Card) Pipeline Intelligence demo: Salesforce pipeline analytics for commercial leaders - where the funnel stalls, with drill-downs and driver insights. Synthetic data.';

-- Lakeflow Connect Salesforce destination: one file per Salesforce object (API field names).
-- Read by the pipeline's bronze layer; this is the governed source for the demo.
CREATE VOLUME IF NOT EXISTS fe_demo_catalog.northwind_pipeline.landing_sfdc
COMMENT 'Mock Lakeflow Connect Salesforce destination: Account, Lead, Opportunity, OpportunityHistory, Campaign, CampaignMember, User, with Salesforce API field names. Pipeline input only. Synthetic.';

-- Other source-system drops (Outreach call exports). Read by the pipeline only.
CREATE VOLUME IF NOT EXISTS fe_demo_catalog.northwind_pipeline.landing
COMMENT 'Raw synthetic Outreach call export for the Northwind Pipeline Intelligence demo. Pipeline input only.';

-- Entity-keyed transcript volume attached to the Genie agent.
CREATE VOLUME IF NOT EXISTS fe_demo_catalog.northwind_pipeline.call_transcripts
COMMENT 'Outreach sales call transcripts for Northwind Commercial Card opportunities, one PDF per call. Each file is keyed by Call ID (CALL-) and lists its Opportunity ID (OPP-) and Account ID (ACCT-), which match the pipeline metric views. Use to explain why deals stall or are lost and what prospects asked for. Numbers come from the metric views.';
