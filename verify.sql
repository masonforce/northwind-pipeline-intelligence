-- =============================================================================
-- Northwind Pipeline Intelligence demo : verify the planted findings through the metric views.
-- These results are the ground truth for the Genie benchmarks in GENIE_AGENT_SETUP.md.
-- =============================================================================

-- 1) Top close-lost reasons for Northwind Commercial Card (expect ERP integration gap first)
SELECT `Close Reason`, MEASURE(`Lost Opportunities`) AS lost, MEASURE(`Lost Volume`) AS lost_volume
FROM fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics
WHERE `Product Line` = 'Northwind Commercial Card' AND `Stage` = 'Closed Lost'
GROUP BY ALL ORDER BY lost DESC;

-- 2) The ERP gap concentrates in NetSuite accounts
SELECT `ERP System`, MEASURE(`Lost Opportunities`) AS erp_gap_losses, MEASURE(`Lost Volume`) AS lost_volume
FROM fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics
WHERE `Product Line` = 'Northwind Commercial Card' AND `Close Reason` = 'ERP integration gap'
GROUP BY ALL ORDER BY erp_gap_losses DESC;

-- 3) Win rate by lead source (expect Partner lowest, Referral highest)
SELECT `Lead Source`, MEASURE(`Win Rate`) AS win_rate, MEASURE(`Opportunities`) AS opps
FROM fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics
GROUP BY ALL ORDER BY win_rate;

-- 4) Launch spike (expect 9/30 and 10/1 far above the prior run rate)
SELECT `Created Date`, MEASURE(`Leads`) AS leads
FROM fe_demo_catalog.northwind_pipeline.demand_inbound_lead_metrics
WHERE `Created Date` >= DATE'2026-09-21'
GROUP BY ALL ORDER BY 1;

-- 5) Campaigns: Launch Webinar = most responses but lowest pipeline per response;
--    CFO Roundtable = few responses, high pipeline per response
SELECT `Campaign`, MEASURE(`Responses`) AS responses, MEASURE(`Attributed Pipeline Volume`) AS pipeline,
       MEASURE(`Pipeline per Response`) AS per_response
FROM fe_demo_catalog.northwind_pipeline.marketing_campaign_metrics
GROUP BY ALL ORDER BY responses DESC;

-- 6) Call themes on lost Northwind Commercial Card deals (expect ERP integration first)
SELECT `Theme`, MEASURE(`Calls on Lost Deals`) AS lost_calls, MEASURE(`Calls`) AS calls
FROM fe_demo_catalog.northwind_pipeline.signal_sales_call_metrics
WHERE `Product Line` = 'Northwind Commercial Card'
GROUP BY ALL ORDER BY lost_calls DESC;

-- 7) FUNNEL STALL: average days in stage for Northwind Commercial Card (expect Solution the longest)
SELECT `Stage`, MEASURE(`Average Days In Stage`) AS avg_days, MEASURE(`Opportunities`) AS opps,
       MEASURE(`Stalled Opportunities`) AS stalled, MEASURE(`Stall Rate`) AS stall_rate
FROM fe_demo_catalog.northwind_pipeline.funnel_stage_metrics
WHERE `Product Line` = 'Northwind Commercial Card'
GROUP BY ALL ORDER BY avg_days DESC;

-- 8) FUNNEL STALL driver: Solution-stage dwell by cohort (expect ERP gap / NetSuite much longer)
SELECT CASE WHEN `Close Reason` = 'ERP integration gap' OR `ERP System` = 'NetSuite' THEN 'ERP gap or NetSuite' ELSE 'Other' END AS cohort,
       MEASURE(`Average Days In Stage`) AS avg_days_in_solution, MEASURE(`Opportunities`) AS opps
FROM fe_demo_catalog.northwind_pipeline.funnel_stage_metrics
WHERE `Product Line` = 'Northwind Commercial Card' AND `Stage` = 'Solution'
GROUP BY ALL ORDER BY avg_days_in_solution DESC;

-- 9) Anchor: OPP-01042 pipeline record
SELECT `Opportunity ID`, `Account ID`, `Account Name`, `ERP System`, `Lead Source`, `Stage`, `Close Reason`,
       MEASURE(`Lost Volume`) AS lost_volume
FROM fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics
WHERE `Opportunity ID` = 'OPP-01042'
GROUP BY ALL;

-- 10) Anchor: OPP-01042 time in each stage (expect a long Solution dwell)
SELECT `Stage`, MEASURE(`Max Days In Stage`) AS days_in_stage, MEASURE(`Stalled Opportunities`) AS stalled
FROM fe_demo_catalog.northwind_pipeline.funnel_stage_metrics
WHERE `Opportunity ID` = 'OPP-01042'
GROUP BY ALL ORDER BY array_position(array('Discovery','Solution','Proposal','Negotiation'), `Stage`);

-- 11) What-if input: lost Northwind Commercial Card volume to the ERP gap (the "recoverable" pool)
SELECT MEASURE(`Lost Volume`) AS erp_lost_volume, MEASURE(`Lost Opportunities`) AS erp_lost_opps
FROM fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics
WHERE `Product Line` = 'Northwind Commercial Card' AND `Close Reason` = 'ERP integration gap';
