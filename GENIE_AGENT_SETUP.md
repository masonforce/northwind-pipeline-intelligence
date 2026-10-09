# Northwind Pipeline Intelligence - Genie agent

One Genie agent, deployed by `deploy_genie_agents.py` (serialized_space v2) so it is reproducible.
Semantics live in the metric-view YAML (`deploy_metric_views.sql`); the agent's text instructions stay
minimal. Ground truth for the benchmarks is in `verify.sql`.

## Agent: Northwind Pipeline Intelligence
- **Metric views (5):** `pipeline_opportunity_metrics`, `funnel_stage_metrics`,
  `demand_inbound_lead_metrics`, `signal_sales_call_metrics`, `marketing_campaign_metrics`.
- **Volume (1):** `call_transcripts` (Outreach PDFs, keyed by CALL-, header lists OPP- and ACCT-).
- **Instructions:** for "where do deals stall", compare Average Days In Stage by Stage in
  `funnel_stage_metrics`, then slice the slow stage by ERP System / Close Reason / Lead Source;
  for a specific OPP-/ACCT-/CALL- give metrics first, then summarize the matching transcript; lead
  with the number.

### Sample questions
- Where do Northwind Commercial Card deals stall in the funnel?
- What's driving the Solution-stage stall?
- Why did OPP-01042 close lost?
- Why are we losing Northwind Commercial Card deals?
- How did inbound demand change after the 9/30 launch?
- Which campaigns drive pipeline, not just engagement?

### Benchmarks (phrasings -> ground-truth SQL)
Covered in `deploy_genie_agents.py` (`benchmarks`): funnel stall by stage, Solution-stage driver by
ERP, stalled open opportunities, OPP-01042, top loss reasons, ERP-gap concentration in NetSuite, win
rate by source, launch spike, campaign quality, lost-deal call themes, ERP-gap recovery, open pipeline
and win rate. Each has 2-3 phrasings; expected answers match `verify.sql`.

## Important: volumes vs metric views
The Genie Conversation API and the per-agent MCP answer from the **metric views only** - they do not
read the attached volume. To blend transcript quotes with the numbers, use the **`northwind-documents`**
UC-functions MCP (`northwind_documents(id)` / `northwind_search_documents(phrase)`) alongside the agent. The app
has its own ID -> transcript panel for the same reason. See `claude-demo/` for the working pattern
(agent MCP for numbers + functions MCP for transcripts, called in parallel).

## Permissions / compute
Genie agents need a Pro or serverless SQL warehouse and the workspace's partner-powered AI features
enabled. Content-search indexing on the volume is enabled in the UI.
