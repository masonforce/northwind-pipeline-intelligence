-- Silver: map the Salesforce connector shape (API field names) to the governed Northwind model, type
-- and clean it. Three pieces of real work happen here:
--   1. Salesforce API fields -> Northwind business columns (the connector-to-model mapping).
--   2. Free-text product interest is normalized into one governed product line, so Northwind Commercial Card
--      demand can be separated from other Northwind products.
--   3. OpportunityHistory becomes per-stage dwell time (days in stage) - the funnel-stall signal -
--      and AI Functions tag each call transcript with a theme and sentiment.

CREATE OR REFRESH MATERIALIZED VIEW silver_accounts AS
SELECT Northwind_Account_Key__c AS account_id, Name AS account_name, Industry AS industry,
       Revenue_Band__c AS revenue_band, CAST(NumberOfEmployees AS INT) AS employee_count,
       BillingState AS hq_state, ERP_System__c AS erp_system,
       Type = 'Customer - Existing' AS existing_northwind_customer,
       CAST(Bill_Pay_Beta__c AS BOOLEAN) AS bill_pay_beta
FROM bronze_sf_account
WHERE NOT CAST(IsDeleted AS BOOLEAN);

CREATE OR REFRESH MATERIALIZED VIEW silver_leads AS
SELECT Northwind_Lead_Key__c AS lead_id, Northwind_Account_Key__c AS account_id,
       CAST(CreatedDate AS DATE) AS created_date, LeadSource AS lead_source,
       Product_Interest__c AS product_interest_raw,
       CASE WHEN lower(Product_Interest__c) RLIKE 'bill pay|accounts payable|ap automation' THEN 'Bill Pay'
            WHEN lower(Product_Interest__c) RLIKE 'northwind corp|corporate platform' THEN 'Northwind Commercial Card'
            ELSE 'Other Northwind Products' END AS product_line,
       NULLIF(Northwind_Campaign_Key__c, '') AS campaign_id,
       CASE Status WHEN 'Closed - Converted' THEN 'Converted' WHEN 'Closed - Not Converted' THEN 'Disqualified'
                   WHEN 'Nurturing' THEN 'Nurture' ELSE 'Open' END AS lead_status
FROM bronze_sf_lead
WHERE NOT CAST(IsDeleted AS BOOLEAN);

CREATE OR REFRESH MATERIALIZED VIEW silver_opportunities AS
SELECT o.Northwind_Opportunity_Key__c AS opportunity_id, a.Northwind_Account_Key__c AS account_id,
       o.Northwind_Lead_Key__c AS lead_id, o.LeadSource AS lead_source,
       c.Northwind_Campaign_Key__c AS campaign_id, u.Name AS owner,
       CASE WHEN lower(o.Product_Interest__c) RLIKE 'bill pay|accounts payable|ap automation' THEN 'Bill Pay'
            WHEN lower(o.Product_Interest__c) RLIKE 'northwind corp|corporate platform' THEN 'Northwind Commercial Card'
            ELSE 'Other Northwind Products' END AS product_line,
       CAST(o.CreatedDate AS DATE) AS created_date, CAST(o.CloseDate AS DATE) AS close_date,
       o.StageName AS stage, CAST(o.Projected_Annual_Volume__c AS BIGINT) AS projected_annual_volume,
       NULLIF(o.Loss_Reason__c, '') AS close_reason, NULLIF(o.Competitor__c, '') AS competitor,
       o.Id AS sfdc_opportunity_id
FROM bronze_sf_opportunity o
JOIN bronze_sf_account a ON o.AccountId = a.Id
JOIN bronze_sf_user u ON o.OwnerId = u.Id
LEFT JOIN bronze_sf_campaign c ON o.CampaignId = c.Id
WHERE NOT CAST(o.IsDeleted AS BOOLEAN);

-- Per-stage dwell time from OpportunityHistory. days_in_stage = time to the next stage change
-- (or to the as-of date for the current stage). The planted stall shows up as long Solution dwell
-- for ERP-gap / NetSuite deals.
CREATE OR REFRESH MATERIALIZED VIEW silver_opportunity_history
COMMENT 'One row per opportunity stage entry with days spent in that stage (from Salesforce OpportunityHistory).'
AS WITH h AS (
  SELECT oh.OpportunityId AS sfdc_opportunity_id, oh.StageName AS stage,
         CAST(oh.CreatedDate AS TIMESTAMP) AS entered_at,
         LEAD(CAST(oh.CreatedDate AS TIMESTAMP)) OVER (PARTITION BY oh.OpportunityId ORDER BY CAST(oh.CreatedDate AS TIMESTAMP)) AS next_at
  FROM bronze_sf_opportunity_history oh
  WHERE NOT CAST(oh.IsDeleted AS BOOLEAN)
)
SELECT o.opportunity_id, o.account_id, o.product_line, o.lead_source, o.close_reason,
       o.stage AS final_stage, o.projected_annual_volume,
       h.stage, CAST(h.entered_at AS DATE) AS entered_date,
       h.next_at IS NULL AS is_current_stage,
       datediff(coalesce(CAST(h.next_at AS DATE), DATE'2026-10-01'), CAST(h.entered_at AS DATE)) AS days_in_stage
FROM h JOIN silver_opportunities o ON h.sfdc_opportunity_id = o.sfdc_opportunity_id
WHERE h.stage IN ('Discovery', 'Solution', 'Proposal', 'Negotiation');

CREATE OR REFRESH MATERIALIZED VIEW silver_campaigns AS
SELECT Northwind_Campaign_Key__c AS campaign_id, Name AS campaign_name, Type AS channel,
       CAST(StartDate AS DATE) AS start_date, CAST(BudgetedCost AS BIGINT) AS budget_usd
FROM bronze_sf_campaign;

CREATE OR REFRESH MATERIALIZED VIEW silver_campaign_responses AS
SELECT cm.Id AS response_id, c.Northwind_Campaign_Key__c AS campaign_id,
       CAST(cm.FirstRespondedDate AS DATE) AS response_date, cm.Northwind_Account_Key__c AS account_id,
       cm.Response_Type__c AS response_type, l.Northwind_Lead_Key__c AS lead_id
FROM bronze_sf_campaign_member cm
JOIN bronze_sf_campaign c ON cm.CampaignId = c.Id
LEFT JOIN bronze_sf_lead l ON cm.LeadId = l.Id;

CREATE OR REFRESH MATERIALIZED VIEW silver_call_signals
COMMENT 'Outreach calls enriched with AI Functions on the prospect''s words only: primary theme (ai_classify) and sentiment (ai_analyze_sentiment).'
AS WITH calls AS (
  SELECT *, concat_ws('\n', filter(split(transcript, '\n'), l -> l NOT LIKE '%(Northwind):%')) AS prospect_text
  FROM bronze_outreach_calls
)
SELECT call_id, opportunity_id, account_id, CAST(call_date AS DATE) AS call_date, rep,
       CAST(duration_sec AS INT) AS duration_sec, transcript,
       ai_classify(prospect_text, ARRAY('ERP integration', 'Approval workflows', 'Vendor card acceptance',
                                        'Pricing & rewards', 'Onboarding & implementation',
                                        'Bill Pay interest', 'Expense policy controls')) AS primary_theme,
       ai_analyze_sentiment(prospect_text) AS sentiment,
       regexp_extract(transcript, '(Ramp|Brex|Navan|Bill\\.com)', 1) AS competitor_mentioned
FROM calls;
