-- Denormalized single-deal serving source for Lakebase: one row per opportunity.
-- Synced (SNAPSHOT) to Lakebase `northwind`.public.deals and point-looked-up by the app's deal detail card.
-- Aggregates stay on the lakehouse (metric views); individual records serve from Lakebase (Postgres).

CREATE TABLE IF NOT EXISTS fe_demo_catalog.northwind_pipeline.gold_serving_deals (
  opportunity_id          STRING NOT NULL,
  account_id              STRING,
  account_name            STRING,
  industry                STRING,
  revenue_band            STRING,
  erp_system              STRING,
  product_line            STRING,
  lead_source             STRING,
  stage                   STRING,
  projected_annual_volume DOUBLE,
  close_reason            STRING,
  competitor              STRING,
  is_stalled              BOOLEAN,
  days_in_stage           INT,
  created_date            DATE,
  close_date              DATE
) TBLPROPERTIES (delta.enableChangeDataFeed = true);

INSERT OVERWRITE fe_demo_catalog.northwind_pipeline.gold_serving_deals
SELECT o.opportunity_id, o.account_id, a.account_name, a.industry, a.revenue_band, a.erp_system,
       o.product_line, o.lead_source, o.stage, CAST(o.projected_annual_volume AS DOUBLE),
       o.close_reason, o.competitor,
       COALESCE(s.is_stalled, false) AS is_stalled, CAST(s.days_in_stage AS INT) AS days_in_stage,
       o.created_date, o.close_date
FROM fe_demo_catalog.northwind_pipeline.gold_fact_opportunities o
LEFT JOIN fe_demo_catalog.northwind_pipeline.gold_dim_account a
  ON o.account_id = a.account_id
LEFT JOIN (SELECT opportunity_id, is_stalled, days_in_stage
           FROM fe_demo_catalog.northwind_pipeline.gold_fact_opportunity_stage
           WHERE is_current_stage = true) s
  ON o.opportunity_id = s.opportunity_id;
