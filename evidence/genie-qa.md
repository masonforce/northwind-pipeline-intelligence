# Genie evidence — Northwind Pipeline Intelligence agent

Live Q&A against the governed metric views (real model output). Space answers from the
semantic layer and returns the governed SQL it ran.

## Q: Where do Northwind Commercial Card deals stall in the funnel, and what's driving it?

**status:** COMPLETED

**Governed SQL Genie ran:**
```sql
WITH `stage_summary` AS (
  SELECT
    `Stage`,
    MEASURE(`Average Days In Stage`) AS `avg_days_in_stage`,
    MEASURE(`Stall Rate`) AS `stall_rate`,
    MEASURE(`Stalled Opportunities`) AS `stalled_opportunities`
  FROM `fe_demo_catalog`.`northwind_pipeline`.`funnel_stage_metrics`
  WHERE `Product Line` = 'Northwind Commercial Card'
    AND `Stage` IS NOT NULL
  GROUP BY ALL
),
`solution_drivers` AS (
  SELECT
    `ERP System`,
    MEASURE(`Average Days In Stage`) AS `avg_days_in_stage`,
    MEASURE(`Stall Rate`) AS `stall_rate`,
    MEASURE(`Stalled Opportunities`) AS `stalled_opportunities`,
    MEASURE(`Stalled Open Pipeline`) AS `stalled_open_pipeline`
  FROM `fe_demo_catalog`.`northwind_pipeline`.`funnel_stage_metrics`
  WHERE `Product Line` = 'Northwind Commercial Card'
    AND `Stage` = 'Solution'
    AND `ERP System` IS NOT NULL
  GROUP BY ALL
),
`close_reason_drivers` AS (
  SELECT
    `Close Reason`,
    MEASURE(`Average Days In Stage`) AS `avg_days_in_stage`,
    MEASURE(`Stall Rate`) AS `stall_rate`,
    MEASURE(`Stalled Opportunities`) AS `stalled_opportunities`
  FROM `fe_demo_catalog`.`northwind_pipeline`.`funnel_stage_metrics`
  WHERE `Product Line` = 'Northwind Commercial Card'
    AND `Stage` = 'Solution'
    AND `Close Reason` IS NOT NULL
  GROUP BY ALL
),
`lead_source_drivers` AS (
  SELECT
    `Lead Source`,
    MEASURE(`Average Days In Stage`) AS `avg_days_in_stage`,
    MEASURE(`Stall Rate`) AS `stall_rate`,
    MEASURE(`Stalled Opportunities`) AS `stalled_opportunities`
  FROM `fe_demo_catalog`.`northwind_pipeline`.`funnel_stage_metrics`
  WHERE `Product Line` = 'Northwind Commercial Card'
    AND `Stage` = 'Solution'
    AND `Lead Source` IS NOT NULL
  GROUP BY ALL
)
SELECT 'stage_summary' AS `section`, `Stage` AS `dimension`, `avg_days_in_stage`, `stall_rate`, `stalled_opportunities`, CAST(NULL AS BIGINT) AS `stalled_open_pipeline`
FROM `stage_summary`
UNION ALL
SELECT 'solution_driver_erp' AS `section`, `ERP System` AS `dimension`, `avg_days_in_stage`, `stall_rate`, `stalled_opportunities`, `stalled_open_pipeline`
FROM `solution_drivers`
UNION ALL
SELECT 'solution_driver_close_reason' AS `section`, `Close Reason` AS `dimension`, `avg_days_in_stage`, `stall_rate`, `stalled_opportunities`, CAST(NULL AS BIGINT) AS `stalled_open_pipeline`
FROM `close_reason_drivers`
UNION ALL
SELECT 'solution_driver_lead_source' AS `section`, `Lead Source` AS `dimension`, `avg_days_in_stage`, `stall_rate`, `stalled_opportunities`, CAST(NULL AS BIGINT) AS `stalled_open_pipeline`
FROM `lead_source_drivers`
```

_You're looking to understand where Northwind Commercial Card deals tend to stall in the sales funnel and what factors are driving these stalls, specifically focusing on the Solution stage. The query breaks down average days deals spend in each funnel stage, the stall rate, and the number of stalled opportunities. It then drills into the Solution stage to analyze these metrics by ERP system, close reason, and lead source to identify key drivers of stalls._

**Answer:**

**28.4 days**: Northwind Commercial Card deals stall most in the **Solution** stage, which has the longest average time in stage and a **24.4%** stall rate, slightly above **Discovery** at **23.0 days** and **23.6%**.

Within Solution, the strongest drivers in the visible data are **ERP integration gap** with **52.6 days** and a **75.0%** stall rate, **NetSuite** with **39.6 days**, **45.7%** stalled, and **12,123,000** in stalled open pipeline, and **Outbound** leads with **47.4 days** and a **60.0%** stall rate.

## Q: Why did OPP-01042 close lost, and how much pipeline is at risk from the same issue?

**status:** COMPLETED

**Governed SQL Genie ran:**
```sql
WITH opp AS (
  SELECT
    `Opportunity ID`,
    `Account Name`,
    `Product Line`,
    `Stage`,
    `Close Reason`,
    `ERP System`,
    `Lead Source`,
    `Competitor`,
    MEASURE(`Lost Volume`) AS `lost_volume`
  FROM fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics
  WHERE `Opportunity ID` = 'OPP-01042'
  GROUP BY ALL
),
same_issue_losses AS (
  SELECT
    `Close Reason`,
    `Product Line`,
    MEASURE(`Lost Opportunities`) AS `same_issue_lost_opportunities`,
    MEASURE(`Lost Volume`) AS `same_issue_lost_volume`
  FROM fe_demo_catalog.northwind_pipeline.pipeline_opportunity_metrics
  WHERE `Stage` = 'Closed Lost' AND `Close Reason` IS NOT NULL
  GROUP BY ALL
)
SELECT
  o.`Opportunity ID`,
  o.`Account Name`,
  o.`Product Line`,
  o.`Stage`,
  o.`Close Reason`,
  o.`ERP System`,
  o.`Lead Source`,
  o.`Competitor`,
  o.`lost_volume`,
  sil.`same_issue_lost_opportunities`,
  sil.`same_issue_lost_volume`
FROM opp o
LEFT JOIN same_issue_losses sil
  ON o.`Close Reason` = sil.`Close Reason`
 AND o.`Product Line` = sil.`Product Line`
```

_You want to see the details of the opportunity with ID OPP-01042, including why it was lost and the amount of lost pipeline volume for that opportunity. Additionally, you want to know the total number of lost opportunities and lost pipeline volume for all opportunities that were lost for the same reason and product line._

**Answer:**

**OPP-01042** closed lost with close reason **ERP integration gap** and had lost pipeline of **$9.4M**. For the same issue in **Other Northwind Products**, there are **34** closed-lost opportunities totaling **$215.7M** in lost pipeline, which shows this issue has affected multiple deals in that product line.
