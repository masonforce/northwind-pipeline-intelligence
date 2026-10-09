-- =============================================================================
-- Northwind Pipeline Intelligence demo : UC metric views (the governed semantic layer)
-- Target: fe_demo_catalog.northwind_pipeline   Run after the pipeline (pipeline/).
--
-- One fact per view. Every view exposes its entity IDs (OPP-, ACCT-, CALL-) as dimensions so
-- Genie can join a question about a specific record to the matching transcript. Routing guidance
-- lives in each view's comment, so the Genie text instructions stay minimal.
--
-- UNITS: rates are percent points (13.0 = 13.0%). "Volume" = projected annual card + payment
-- volume in USD, the pipeline currency for Northwind Commercial Card. Days are calendar days.
-- Requires a Pro or serverless SQL warehouse (metric-view YAML v1.1).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. pipeline_opportunity_metrics  (pipeline, win rate, deal size, loss reasons)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
comment: "Governed Salesforce opportunity metrics for Northwind Commercial Card, Bill Pay and other Northwind business products. One row per opportunity (OPP-). Use for pipeline, win rate, deal size, sales cycle, and close-lost reasons, sliced by product line, lead source, campaign, segment, industry and ERP system. Use Product Line = 'Northwind Commercial Card' to separate Northwind Commercial Card demand from other products. For where deals stall in the funnel use funnel_stage_metrics; for lead volume and the launch spike use demand_inbound_lead_metrics; for why a deal was lost, read the call transcripts for that Opportunity ID. Rates are percent points; volume is projected annual volume in USD."
source: fe_demo_catalog.northwind_pipeline.gold_fact_opportunities
joins:
  - name: account
    source: fe_demo_catalog.northwind_pipeline.gold_dim_account
    "on": source.account_id = account.account_id
  - name: campaign
    source: fe_demo_catalog.northwind_pipeline.gold_dim_campaign
    "on": source.campaign_id = campaign.campaign_id
dimensions:
  - {name: Opportunity ID, expr: opportunity_id, comment: "Salesforce opportunity ID, e.g. OPP-01042. Matches the Opportunity ID in call transcripts.", synonyms: [opp, deal, opportunity]}
  - {name: Account ID, expr: source.account_id, comment: "Account ID, e.g. ACCT-0317.", synonyms: [customer ID, company ID]}
  - {name: Account Name, expr: account.account_name, comment: "Company name.", synonyms: [company, customer, prospect]}
  - {name: Product Line, expr: product_line, comment: "'Northwind Commercial Card' (the Northwind corporate card and expense platform), 'Bill Pay', or 'Other Northwind Products', normalized from free-text product interest. 'Northwind Commercial Card demand' or 'Northwind Commercial Card deals' means Product Line = 'Northwind Commercial Card' only.", synonyms: [product, Northwind, Northwind Commercial Card deals]}
  - {name: Lead Source, expr: lead_source, comment: "'Inbound Web', 'Paid Search', 'Partner', 'Referral', 'Event', 'Outbound'.", synonyms: [source, channel, origin]}
  - {name: Campaign, expr: campaign.campaign_name, comment: "Marketing campaign that sourced the lead; NULL if none.", synonyms: [campaign name]}
  - {name: Owner, expr: owner, comment: "Opportunity owner (seller).", synonyms: [rep, seller, AE]}
  - {name: Stage, expr: stage, comment: "'Discovery', 'Solution', 'Proposal', 'Negotiation' (open) or 'Closed Won', 'Closed Lost'.", synonyms: [opportunity stage, status]}
  - {name: Is Open, expr: NOT is_closed, comment: "True for open (not yet closed) opportunities. 'Pipeline' with no other qualifier means open opportunities only.", synonyms: [open pipeline, active deals, in pipeline]}
  - {name: Close Reason, expr: close_reason, comment: "Why a Closed Lost deal was lost: 'ERP integration gap', 'Chose competitor', 'Pricing / rewards', 'Timing', 'No decision'. NULL unless Closed Lost.", synonyms: [loss reason, lost reason, why lost, ERP losses]}
  - {name: Competitor, expr: competitor, comment: "Competitor chosen when Close Reason = 'Chose competitor': Ramp, Brex, Navan, Bill.com.", synonyms: [competition]}
  - {name: Revenue Band, expr: account.revenue_band, comment: "'$10M-$50M', '$50M-$250M', '$250M-$1B'.", synonyms: [segment, company size, middle market band]}
  - {name: Industry, expr: account.industry, comment: "Account industry, e.g. 'Manufacturing', 'Healthcare', 'Technology'.", synonyms: [vertical, sector]}
  - {name: ERP System, expr: account.erp_system, comment: "Account's ERP: NetSuite, QuickBooks Online, Sage Intacct, Microsoft Dynamics 365, SAP Business One, Other.", synonyms: [ERP, accounting system]}
  - {name: Existing Northwind Customer, expr: account.existing_northwind_customer, comment: "True if the company already holds Northwind products.", synonyms: [existing customer, cross-sell]}
  - {name: Created Month, expr: "CAST(DATE_TRUNC('MONTH', created_date) AS DATE)", comment: "Month the opportunity was created.", synonyms: [created, open month], format: {type: date, date_format: locale_short_month}}
  - {name: Close Month, expr: "CAST(DATE_TRUNC('MONTH', close_date) AS DATE)", comment: "Month the opportunity closed (or is expected to close if open).", format: {type: date, date_format: locale_short_month}}
  - {name: Close Quarter, expr: "CONCAT('Q', QUARTER(close_date), ' ', YEAR(close_date))", comment: "Calendar quarter of close, e.g. 'Q3 2026'."}
measures:
  - {name: Opportunities, expr: COUNT(1), comment: "Count of opportunities.", synonyms: [deals, opp count], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Open Pipeline Volume, expr: SUM(projected_annual_volume) FILTER (WHERE NOT is_closed), comment: "Projected annual volume (USD) of open opportunities. The default 'pipeline' measure.", synonyms: [pipeline, open pipeline, pipeline value], format: {type: currency, currency_code: USD, decimal_places: {type: exact, places: 1}, abbreviation: compact}}
  - {name: Won Volume, expr: SUM(projected_annual_volume) FILTER (WHERE is_won), comment: "Projected annual volume (USD) of Closed Won opportunities.", synonyms: [bookings, won pipeline], format: {type: currency, currency_code: USD, decimal_places: {type: exact, places: 1}, abbreviation: compact}}
  - {name: Lost Volume, expr: SUM(projected_annual_volume) FILTER (WHERE is_lost), comment: "Projected annual volume (USD) of Closed Lost opportunities. Slice by Close Reason to size a loss reason. For what-if recovery questions (e.g. closing the ERP gap), this is the upper bound and assumes every lost deal for that reason would have converted; say so.", synonyms: [lost pipeline, lost revenue], format: {type: currency, currency_code: USD, decimal_places: {type: exact, places: 1}, abbreviation: compact}}
  - {name: Won Opportunities, expr: COUNT_IF(is_won), comment: "Count of Closed Won opportunities.", synonyms: [wins], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Lost Opportunities, expr: COUNT_IF(is_lost), comment: "Count of Closed Lost opportunities.", synonyms: [losses], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Closed Opportunities, expr: COUNT_IF(is_closed), comment: "Opportunities that are Closed Won or Closed Lost.", synonyms: [closed deals], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Win Rate, expr: "100.0 * MEASURE(`Won Opportunities`) / NULLIF(MEASURE(`Closed Opportunities`), 0)", comment: "Won / closed opportunities, in percent points. Open deals excluded.", synonyms: [close rate, conversion to win], format: {type: number, decimal_places: {type: exact, places: 1}}}
  - {name: Average Deal Volume, expr: AVG(projected_annual_volume), comment: "Average projected annual volume per opportunity (USD).", synonyms: [deal size, average deal size], format: {type: currency, currency_code: USD, decimal_places: {type: exact, places: 1}, abbreviation: compact}}
  - {name: Average Sales Cycle Days, expr: AVG(cycle_days), comment: "Average days from created to close, closed deals only.", synonyms: [sales cycle, cycle time, days to close], format: {type: number, decimal_places: {type: exact, places: 0}}}
$$;

-- ---------------------------------------------------------------------------
-- 2. funnel_stage_metrics  (where deals stall: dwell time by stage)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW fe_demo_catalog.northwind_pipeline.funnel_stage_metrics
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
comment: "Governed funnel-stage dwell metrics from Salesforce OpportunityHistory: one row per opportunity per stage it entered (Discovery, Solution, Proposal, Negotiation). Use to find WHERE in the funnel deals stall - average and max days in each stage, how many opportunities are stalled (days in stage above the 75th percentile for that stage), and the stall rate - sliced by stage, product line, lead source, segment, ERP system and close reason. For Northwind Commercial Card deals the stall concentrates in the Solution stage, worst for NetSuite and ERP-gap deals; read the call transcripts for a stalled Opportunity ID to see the driver. One opportunity appears once per stage, so count opportunities with COUNT(DISTINCT), and use the current-stage measures for live open pipeline. Days are calendar days; rates are percent points; volume is projected annual volume in USD."
source: fe_demo_catalog.northwind_pipeline.gold_fact_opportunity_stage
dimensions:
  - {name: Opportunity ID, expr: opportunity_id, comment: "Salesforce opportunity ID, e.g. OPP-01042. Matches the Opportunity ID in call transcripts.", synonyms: [opp, deal, opportunity]}
  - {name: Account ID, expr: account_id, comment: "Account ID, e.g. ACCT-0317."}
  - {name: Account Name, expr: account_name, comment: "Company name.", synonyms: [company, customer, prospect]}
  - {name: Stage, expr: stage, comment: "Funnel stage the dwell time is measured in: 'Discovery', 'Solution', 'Proposal', 'Negotiation'.", synonyms: [funnel stage, pipeline stage]}
  - {name: Is Current Stage, expr: is_current_stage, comment: "True if this is the stage the opportunity is in now (open deals) or the last stage before it closed. Use for the live/open funnel.", synonyms: [current stage, now]}
  - {name: Is Stalled, expr: is_stalled, comment: "True when days in this stage exceed the 75th percentile for that stage across all deals. The stall flag.", synonyms: [stalled, stuck, slow]}
  - {name: Product Line, expr: product_line, comment: "'Northwind Commercial Card', 'Bill Pay', or 'Other Northwind Products'. 'Northwind Commercial Card deals' means Product Line = 'Northwind Commercial Card' only.", synonyms: [product, Northwind, Northwind Commercial Card deals]}
  - {name: Lead Source, expr: lead_source, comment: "'Inbound Web', 'Paid Search', 'Partner', 'Referral', 'Event', 'Outbound'.", synonyms: [source, channel]}
  - {name: Close Reason, expr: close_reason, comment: "Loss reason if the deal ultimately closed lost: 'ERP integration gap', 'Chose competitor', 'Pricing / rewards', 'Timing', 'No decision'. NULL if open or won.", synonyms: [loss reason, why lost]}
  - {name: Final Stage, expr: final_stage, comment: "The opportunity's current/terminal stage, incl. 'Closed Won' / 'Closed Lost'."}
  - {name: Revenue Band, expr: revenue_band, comment: "'$10M-$50M', '$50M-$250M', '$250M-$1B'.", synonyms: [segment, company size]}
  - {name: Industry, expr: industry, comment: "Account industry.", synonyms: [vertical]}
  - {name: ERP System, expr: erp_system, comment: "Account's ERP: NetSuite, QuickBooks Online, Sage Intacct, Microsoft Dynamics 365, SAP Business One, Other.", synonyms: [ERP, accounting system]}
  - {name: Entered Month, expr: "CAST(DATE_TRUNC('MONTH', entered_date) AS DATE)", comment: "Month the opportunity entered this stage.", synonyms: [month], format: {type: date, date_format: locale_short_month}}
measures:
  - {name: Stage Entries, expr: COUNT(1), comment: "Count of opportunity-stage entries.", synonyms: [entries], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Opportunities, expr: COUNT(DISTINCT opportunity_id), comment: "Distinct opportunities.", synonyms: [deals], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Average Days In Stage, expr: AVG(days_in_stage), comment: "Average calendar days spent in the stage. The core 'where do deals stall' measure; group by Stage.", synonyms: [avg days in stage, dwell time, time in stage, aging], format: {type: number, decimal_places: {type: exact, places: 1}}}
  - {name: Median Days In Stage, expr: "percentile_approx(days_in_stage, 0.5)", comment: "Median calendar days spent in the stage.", synonyms: [median dwell], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Max Days In Stage, expr: MAX(days_in_stage), comment: "Longest dwell in the stage.", format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Stalled Opportunities, expr: COUNT(DISTINCT opportunity_id) FILTER (WHERE is_stalled), comment: "Distinct opportunities stalled in this stage (days in stage above the 75th percentile).", synonyms: [stalled deals, stuck deals], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Stall Rate, expr: "100.0 * MEASURE(`Stalled Opportunities`) / NULLIF(MEASURE(`Opportunities`), 0)", comment: "Share of opportunities in the stage that are stalled, percent points.", synonyms: [percent stalled], format: {type: number, decimal_places: {type: exact, places: 1}}}
  - {name: Stalled Open Pipeline, expr: SUM(projected_annual_volume) FILTER (WHERE is_stalled AND is_current_stage), comment: "Projected annual volume (USD) of open opportunities stalled in their current stage.", synonyms: [stalled pipeline, at-risk pipeline], format: {type: currency, currency_code: USD, decimal_places: {type: exact, places: 1}, abbreviation: compact}}
$$;

-- ---------------------------------------------------------------------------
-- 3. demand_inbound_lead_metrics  (lead volume, launch spike)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW fe_demo_catalog.northwind_pipeline.demand_inbound_lead_metrics
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
comment: "Governed inbound demand metrics: one row per Salesforce lead (LEAD-), Oct 2025 - Oct 1 2026. Use for lead volume, the 9/30/2026 Northwind Commercial Card launch spike, lead-to-opportunity conversion, and demand by product line, source, campaign and segment. Northwind Commercial Card GA launched 2026-09-30; early access opened 2026-04-01. For pipeline dollars and win rate use pipeline_opportunity_metrics. Rates are percent points."
source: fe_demo_catalog.northwind_pipeline.gold_fact_leads
joins:
  - name: account
    source: fe_demo_catalog.northwind_pipeline.gold_dim_account
    "on": source.account_id = account.account_id
  - name: campaign
    source: fe_demo_catalog.northwind_pipeline.gold_dim_campaign
    "on": source.campaign_id = campaign.campaign_id
dimensions:
  - {name: Lead ID, expr: lead_id, comment: "Salesforce lead ID, e.g. LEAD-00151."}
  - {name: Account ID, expr: source.account_id, comment: "Account ID, e.g. ACCT-0317."}
  - {name: Created Date, expr: created_date, comment: "Date the lead was created.", synonyms: [date, day], format: {type: date, date_format: year_month_day}}
  - {name: Created Week, expr: "CAST(DATE_TRUNC('WEEK', created_date) AS DATE)", comment: "Week (Monday start) the lead was created.", synonyms: [week], format: {type: date, date_format: year_week}}
  - {name: Created Month, expr: "CAST(DATE_TRUNC('MONTH', created_date) AS DATE)", comment: "Month the record was created.", synonyms: [month], format: {type: date, date_format: locale_short_month}}
  - {name: Launch Period, expr: "CASE WHEN created_date >= DATE'2026-09-30' THEN 'Post-launch (GA)' WHEN created_date >= DATE'2026-04-01' THEN 'Early access' ELSE 'Pre-early access' END", comment: "'Pre-early access' (before 2026-04-01), 'Early access' (2026-04-01 to 2026-09-29), 'Post-launch (GA)' (from 2026-09-30).", synonyms: [launch, before and after launch, since launch, post-GA]}
  - {name: Product Line, expr: product_line, comment: "'Northwind Commercial Card' (the Northwind corporate card and expense platform), 'Bill Pay', or 'Other Northwind Products', normalized from free-text product interest. 'Northwind Commercial Card demand' means Product Line = 'Northwind Commercial Card' only.", synonyms: [product, Northwind, Northwind Commercial Card deals]}
  - {name: Product Interest (Raw), expr: product_interest_raw, comment: "Original free-text product interest from the web form or seller. Use Product Line for analysis."}
  - {name: Lead Source, expr: lead_source, comment: "'Inbound Web', 'Paid Search', 'Partner', 'Referral', 'Event', 'Outbound'.", synonyms: [source, channel]}
  - {name: Campaign, expr: campaign.campaign_name, comment: "Marketing campaign name; NULL if none.", synonyms: [campaign name]}
  - {name: Lead Status, expr: lead_status, comment: "'Open', 'Converted', 'Nurture', 'Disqualified'."}
  - {name: Revenue Band, expr: account.revenue_band, comment: "'$10M-$50M', '$50M-$250M', '$250M-$1B'.", synonyms: [segment, company size]}
  - {name: Industry, expr: account.industry, comment: "Account industry, e.g. 'Manufacturing', 'Healthcare', 'Technology'.", synonyms: [vertical]}
  - {name: ERP System, expr: account.erp_system, comment: "Account's ERP: NetSuite, QuickBooks Online, Sage Intacct, Microsoft Dynamics 365, SAP Business One, Other.", synonyms: [ERP]}
measures:
  - {name: Leads, expr: COUNT(1), comment: "Count of leads.", synonyms: [inbound demand, lead volume, inbound leads], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Average Daily Leads, expr: "MEASURE(`Leads`) / NULLIF(COUNT(DISTINCT created_date), 0)", comment: "Leads per day with activity. Compare launch days to the prior average.", synonyms: [leads per day, daily run rate], format: {type: number, decimal_places: {type: exact, places: 1}}}
  - {name: Converted Leads, expr: COUNT_IF(converted_to_opportunity), comment: "Leads that became an opportunity.", synonyms: [leads converted], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Lead Conversion Rate, expr: "100.0 * MEASURE(`Converted Leads`) / NULLIF(MEASURE(`Leads`), 0)", comment: "Share of leads that became opportunities, percent points. Recent leads (under ~2 weeks old) have not had time to convert.", synonyms: [conversion rate, lead to opp rate], format: {type: number, decimal_places: {type: exact, places: 1}}}
  - {name: Accounts Generating Leads, expr: COUNT(DISTINCT source.account_id), comment: "Distinct accounts with at least one lead.", synonyms: [unique companies], format: {type: number, decimal_places: {type: exact, places: 0}}}
$$;

-- ---------------------------------------------------------------------------
-- 4. signal_sales_call_metrics  (what prospects talk about: drivers)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW fe_demo_catalog.northwind_pipeline.signal_sales_call_metrics
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
comment: "Governed customer-signal metrics from Outreach sales calls: one row per call (CALL-), with the AI-extracted primary theme and sentiment and the opportunity outcome. Use for which themes come up most, which themes show up in lost or stalled deals, and what is driving outcomes. The full transcript for any Call ID or Opportunity ID is in the call_transcripts volume. Rates are percent points."
source: fe_demo_catalog.northwind_pipeline.gold_fact_call_signals
joins:
  - name: account
    source: fe_demo_catalog.northwind_pipeline.gold_dim_account
    "on": source.account_id = account.account_id
dimensions:
  - {name: Call ID, expr: call_id, comment: "Outreach call ID, e.g. CALL-0003. Matches the transcript file name.", synonyms: [call]}
  - {name: Opportunity ID, expr: opportunity_id, comment: "Opportunity discussed on the call, e.g. OPP-01042.", synonyms: [opp, deal]}
  - {name: Account ID, expr: source.account_id, comment: "Account ID, e.g. ACCT-0317."}
  - {name: Account Name, expr: account.account_name, comment: "Company name.", synonyms: [company, prospect]}
  - {name: Call Date, expr: call_date, comment: "Date of the call.", format: {type: date, date_format: year_month_day}}
  - {name: Call Month, expr: "CAST(DATE_TRUNC('MONTH', call_date) AS DATE)", comment: "Month of the call.", synonyms: [month], format: {type: date, date_format: locale_short_month}}
  - {name: Rep, expr: rep, comment: "Seller who ran the call.", synonyms: [seller, owner]}
  - {name: Theme, expr: primary_theme, comment: "AI-extracted primary theme: 'ERP integration', 'Approval workflows', 'Vendor card acceptance', 'Pricing & rewards', 'Onboarding & implementation', 'Bill Pay interest', 'Expense policy controls'.", synonyms: [topic, objection, customer theme, signal, driver]}
  - {name: Sentiment, expr: sentiment, comment: "AI sentiment of the prospect's words: 'positive', 'neutral', 'negative', 'mixed'."}
  - {name: Competitor Mentioned, expr: competitor_mentioned, comment: "Competitor named on the call (Ramp, Brex, Navan, Bill.com), NULL if none."}
  - {name: Product Line, expr: product_line, comment: "'Northwind Commercial Card', 'Bill Pay', or 'Other Northwind Products'. 'Northwind Commercial Card deals' means Product Line = 'Northwind Commercial Card' only.", synonyms: [product, Northwind, Northwind Commercial Card deals]}
  - {name: Opportunity Stage, expr: opportunity_stage, comment: "Current stage of the discussed opportunity, incl. 'Closed Won' / 'Closed Lost'."}
  - {name: Opportunity Close Reason, expr: opportunity_close_reason, comment: "Close reason of the discussed opportunity if Closed Lost: 'ERP integration gap', 'Chose competitor', 'Pricing / rewards', 'Timing', 'No decision'.", synonyms: [loss reason]}
  - {name: ERP System, expr: account.erp_system, comment: "Account's ERP: NetSuite, QuickBooks Online, Sage Intacct, Microsoft Dynamics 365, SAP Business One, Other.", synonyms: [ERP]}
  - {name: Revenue Band, expr: account.revenue_band, comment: "'$10M-$50M', '$50M-$250M', '$250M-$1B'.", synonyms: [segment]}
measures:
  - {name: Calls, expr: COUNT(1), comment: "Count of sales calls.", synonyms: [call count, mentions], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Opportunities Discussed, expr: COUNT(DISTINCT opportunity_id), comment: "Distinct opportunities with at least one call.", synonyms: [deals discussed], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Calls on Lost Deals, expr: "COUNT_IF(opportunity_stage = 'Closed Lost')", comment: "Calls whose opportunity ended Closed Lost.", format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Negative Calls, expr: "COUNT_IF(sentiment = 'negative')", comment: "Calls with negative prospect sentiment.", format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Calls with Competitor Mention, expr: COUNT_IF(competitor_mentioned IS NOT NULL), comment: "Calls naming Ramp, Brex, Navan or Bill.com.", format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Negative Call Rate, expr: "100.0 * MEASURE(`Negative Calls`) / NULLIF(MEASURE(`Calls`), 0)", comment: "Share of calls with negative prospect sentiment, percent points.", format: {type: number, decimal_places: {type: exact, places: 1}}}
  - {name: Competitor Mention Rate, expr: "100.0 * MEASURE(`Calls with Competitor Mention`) / NULLIF(MEASURE(`Calls`), 0)", comment: "Share of calls naming a competitor, percent points.", format: {type: number, decimal_places: {type: exact, places: 1}}}
$$;

-- ---------------------------------------------------------------------------
-- 5. marketing_campaign_metrics  (response vs pipeline)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW fe_demo_catalog.northwind_pipeline.marketing_campaign_metrics
WITH METRICS LANGUAGE YAML AS $$
version: 1.1
comment: "Governed campaign metrics: one row per campaign response (Salesforce CampaignMember), attributed to the lead and opportunity it produced. Use to compare engagement (responses) with business outcome (leads, opportunities, attributed pipeline, wins) by campaign and channel. Volume is projected annual volume in USD; rates are percent points."
source: fe_demo_catalog.northwind_pipeline.gold_fact_campaign_responses
joins:
  - name: cmp
    source: fe_demo_catalog.northwind_pipeline.gold_dim_campaign
    "on": source.campaign_id = cmp.campaign_id
  - name: account
    source: fe_demo_catalog.northwind_pipeline.gold_dim_account
    "on": source.account_id = account.account_id
dimensions:
  - {name: Campaign ID, expr: source.campaign_id, comment: "e.g. CMP-01."}
  - {name: Campaign, expr: cmp.campaign_name, comment: "Marketing campaign name; NULL if none.", synonyms: [campaign name]}
  - {name: Channel, expr: cmp.channel, comment: "'Webinar', 'Event', 'Paid Search', 'Partner', 'Email', 'Paid Social', 'Referral'.", synonyms: [campaign type, marketing channel]}
  - {name: Campaign Budget, expr: cmp.budget_usd, comment: "Campaign budget in USD (one value per campaign; group by Campaign before comparing)."}
  - {name: Response Type, expr: response_type, comment: "'Registered', 'Attended', 'Clicked', 'Downloaded'."}
  - {name: Response Month, expr: "CAST(DATE_TRUNC('MONTH', response_date) AS DATE)", comment: "Month of the campaign response.", synonyms: [month], format: {type: date, date_format: locale_short_month}}
  - {name: Revenue Band, expr: account.revenue_band, comment: "'$10M-$50M', '$50M-$250M', '$250M-$1B'.", synonyms: [segment]}
measures:
  - {name: Responses, expr: COUNT(1), comment: "Count of campaign responses (registrations, attendance, clicks, downloads).", synonyms: [engagement, campaign responses], format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Leads Generated, expr: COUNT(lead_id), comment: "Responses that produced a lead.", format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Opportunities Generated, expr: COUNT(opportunity_id), comment: "Responses whose lead became an opportunity.", format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Attributed Pipeline Volume, expr: SUM(attributed_pipeline_volume), comment: "Projected annual volume (USD) of opportunities sourced by the campaign, open and closed.", synonyms: [campaign pipeline, sourced pipeline], format: {type: currency, currency_code: USD, decimal_places: {type: exact, places: 1}, abbreviation: compact}}
  - {name: Pipeline per Response, expr: "MEASURE(`Attributed Pipeline Volume`) / NULLIF(MEASURE(`Responses`), 0)", comment: "Attributed pipeline volume per response (USD). The quality-vs-quantity measure.", synonyms: [pipeline efficiency], format: {type: currency, currency_code: USD, decimal_places: {type: exact, places: 0}, abbreviation: compact}}
  - {name: Won Opportunities, expr: COUNT_IF(attributed_won), comment: "Campaign-attributed opportunities that are Closed Won.", format: {type: number, decimal_places: {type: exact, places: 0}}}
  - {name: Response to Opportunity Rate, expr: "100.0 * MEASURE(`Opportunities Generated`) / NULLIF(MEASURE(`Responses`), 0)", comment: "Percent points.", format: {type: number, decimal_places: {type: exact, places: 1}}}
$$;

-- ---------------------------------------------------------------------------
-- Domain / subdomain tags (discoverability). Applied after CREATE OR REPLACE.
-- Keys are semantic_domain / semantic_subdomain because this workspace's tag
-- policy restricts the `domain` key to a fixed value list.
-- ---------------------------------------------------------------------------
ALTER VIEW fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics SET TAGS ('semantic_domain' = 'commercial', 'semantic_subdomain' = 'pipeline');
ALTER VIEW fe_demo_catalog.northwind_pipeline.funnel_stage_metrics SET TAGS ('semantic_domain' = 'commercial', 'semantic_subdomain' = 'funnel_stage');
ALTER VIEW fe_demo_catalog.northwind_pipeline.demand_inbound_lead_metrics SET TAGS ('semantic_domain' = 'commercial', 'semantic_subdomain' = 'demand');
ALTER VIEW fe_demo_catalog.northwind_pipeline.signal_sales_call_metrics SET TAGS ('semantic_domain' = 'commercial', 'semantic_subdomain' = 'customer_signal');
ALTER VIEW fe_demo_catalog.northwind_pipeline.marketing_campaign_metrics SET TAGS ('semantic_domain' = 'commercial', 'semantic_subdomain' = 'marketing');
