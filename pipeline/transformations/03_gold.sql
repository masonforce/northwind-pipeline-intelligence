-- Gold: analysis-ready facts and dimensions. The UC metric views (deploy_metric_views.sql)
-- sit on these. Every fact keeps its entity IDs so transcripts and metrics join on the same key.

CREATE OR REFRESH MATERIALIZED VIEW gold_dim_account
COMMENT 'Middle-market companies (prospects and customers), one row per account. Synthetic.'
AS SELECT * FROM silver_accounts;

CREATE OR REFRESH MATERIALIZED VIEW gold_dim_campaign
COMMENT 'Marketing campaigns.'
AS SELECT * FROM silver_campaigns;

CREATE OR REFRESH MATERIALIZED VIEW gold_fact_leads
COMMENT 'One row per lead, with normalized product line and whether it converted to an opportunity.'
AS SELECT l.*, o.opportunity_id, o.opportunity_id IS NOT NULL AS converted_to_opportunity
FROM silver_leads l LEFT JOIN silver_opportunities o ON l.lead_id = o.lead_id;

CREATE OR REFRESH MATERIALIZED VIEW gold_fact_opportunities
COMMENT 'One row per opportunity with outcome flags and sales cycle length.'
AS SELECT opportunity_id, account_id, lead_id, lead_source, campaign_id, owner, product_line,
       created_date, close_date, stage, projected_annual_volume, close_reason, competitor,
       stage IN ('Closed Won', 'Closed Lost') AS is_closed,
       stage = 'Closed Won' AS is_won,
       stage = 'Closed Lost' AS is_lost,
       CASE WHEN stage IN ('Closed Won', 'Closed Lost') THEN datediff(close_date, created_date) END AS cycle_days
FROM silver_opportunities;

-- Funnel stage dwell with a data-driven stall flag: a stage entry is "stalled" when its days in
-- stage exceed the 75th percentile for that stage across all opportunities. The planted stall makes
-- ERP-gap / NetSuite deals stall in Solution.
CREATE OR REFRESH MATERIALIZED VIEW gold_fact_opportunity_stage
COMMENT 'One row per opportunity per funnel stage (Discovery, Solution, Proposal, Negotiation) with days in stage and a stall flag (days in stage above the 75th percentile for that stage). Built from Salesforce OpportunityHistory.'
AS WITH p AS (
  SELECT stage, percentile_approx(days_in_stage, 0.75) AS p75_days
  FROM silver_opportunity_history GROUP BY stage
)
SELECT h.opportunity_id, h.account_id, h.product_line, h.lead_source, h.close_reason,
       h.final_stage, h.projected_annual_volume, h.stage, h.entered_date, h.is_current_stage,
       h.days_in_stage, p.p75_days,
       h.days_in_stage > p.p75_days AS is_stalled,
       a.account_name, a.revenue_band, a.industry, a.erp_system
FROM silver_opportunity_history h
JOIN p ON h.stage = p.stage
JOIN gold_dim_account a ON h.account_id = a.account_id;

CREATE OR REFRESH MATERIALIZED VIEW gold_fact_call_signals
COMMENT 'One row per Outreach call: AI-extracted theme and sentiment, joined to the opportunity outcome. The full transcript for any Call ID or Opportunity ID is in the call_transcripts volume.'
AS SELECT c.call_id, c.opportunity_id, c.account_id, c.call_date, c.rep, c.duration_sec,
       c.primary_theme, c.sentiment, NULLIF(c.competitor_mentioned, '') AS competitor_mentioned,
       o.product_line, o.stage AS opportunity_stage, o.close_reason AS opportunity_close_reason
FROM silver_call_signals c JOIN gold_fact_opportunities o ON c.opportunity_id = o.opportunity_id;

CREATE OR REFRESH MATERIALIZED VIEW gold_fact_campaign_responses
COMMENT 'One row per campaign response, attributed to the lead and opportunity it produced (if any).'
AS SELECT r.*, l.opportunity_id, o.projected_annual_volume AS attributed_pipeline_volume,
       o.stage = 'Closed Won' AS attributed_won
FROM silver_campaign_responses r
LEFT JOIN gold_fact_leads l ON r.lead_id = l.lead_id
LEFT JOIN gold_fact_opportunities o ON l.opportunity_id = o.opportunity_id;
