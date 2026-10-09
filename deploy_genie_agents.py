#!/usr/bin/env python3
"""
Create or update the Northwind Pipeline Intelligence Genie agent through the Genie Spaces API
(serialized_space v2), so the agent is reproducible instead of hand-built in the UI.

One agent, over the governed commercial semantic layer (5 metric views) plus the call-transcript
volume. Semantics ("pipeline = open deals", "stalled = above the 75th percentile dwell") live in the
metric-view YAML, not here, so the text instructions stay minimal. Benchmarks have 2-4 phrasings per
question with ground truth from verify.sql.

This deploys a NEW Genie space (its own title); it does not touch the broader commercial-loop demo's
agents. Usage:  python3 deploy_genie_agents.py            # create or update
                python3 deploy_genie_agents.py --dry-run  # print payload only
"""

import json
import subprocess
import sys
import uuid

import os

PROFILE = os.environ.get("DATABRICKS_PROFILE", "example-workspace")
WAREHOUSE = os.environ.get("WAREHOUSE_ID", "6c8615d2e291c37f")
PARENT = "/Users/mason.force@databricks.com"
NS = "fe_demo_catalog.northwind_pipeline"
VOL = "/Volumes/fe_demo_catalog/northwind_pipeline"

# Low-cardinality fields that get entity matching (prompt matching on values).
ENTITY_MATCH = {"Product Line", "Lead Source", "Stage", "Final Stage", "Close Reason", "Competitor",
                "ERP System", "Revenue Band", "Industry", "Campaign", "Channel", "Theme", "Sentiment",
                "Launch Period", "Lead Status", "Response Type"}


def sql_lines(sql):
    lines = sql.strip().split("\n")
    return [l + "\n" for l in lines[:-1]] + [lines[-1]]


def q(nl, sql):
    return {"question": nl, "sql": sql}


AGENTS = [
    {
        "title": "Northwind Pipeline Intelligence",
        "description": (
            "Pipeline intelligence for Northwind Commercial Card (Northwind), the corporate card and expense management platform for "
            "middle-market companies, launched September 30, 2026. Answers questions for commercial leaders about the "
            "Salesforce pipeline: where deals stall in the funnel (days in each stage, stall rate, stalled pipeline), win "
            "rate, deal size and sales cycle, why deals are won or lost, inbound demand and the launch spike, campaign "
            "performance (responses vs pipeline), and what prospects say on sales calls (themes, sentiment, ERP and "
            "approval needs). Separates Northwind Commercial Card demand from Bill Pay and other Northwind business products. "
            "Reads Outreach call transcripts for any opportunity (OPP-) or call (CALL-). Synthetic demo data."),
        "views": ["pipeline_opportunity_metrics", "funnel_stage_metrics", "demand_inbound_lead_metrics",
                  "signal_sales_call_metrics", "marketing_campaign_metrics"],
        "volumes": ["call_transcripts"],
        "instructions": [
            "For 'where do deals stall', use funnel_stage_metrics: compare Average Days In Stage by Stage, then slice the slow stage by ERP System, Close Reason or Lead Source to find the driver.",
            "For a question about a specific opportunity, account or call (OPP-, ACCT-, CALL- IDs), give its metrics first, then summarize the call transcripts whose header matches that ID.",
            "Lead with the number or finding, then one line of context.",
        ],
        "examples": [
            q("Where do Northwind Commercial Card deals stall in the funnel?", f"""SELECT `Stage`, MEASURE(`Average Days In Stage`) AS avg_days, MEASURE(`Stall Rate`) AS stall_rate
FROM {NS}.funnel_stage_metrics
WHERE `Product Line` = 'Northwind Commercial Card'
GROUP BY ALL ORDER BY avg_days DESC;"""),
            q("What's driving the stall in the Solution stage?", f"""SELECT `ERP System`, MEASURE(`Average Days In Stage`) AS avg_days, MEASURE(`Stalled Opportunities`) AS stalled
FROM {NS}.funnel_stage_metrics
WHERE `Product Line` = 'Northwind Commercial Card' AND `Stage` = 'Solution'
GROUP BY ALL ORDER BY avg_days DESC;"""),
            q("Why are we losing Northwind Commercial Card deals?", f"""SELECT `Close Reason`, MEASURE(`Lost Opportunities`) AS lost_deals, MEASURE(`Lost Volume`) AS lost_volume
FROM {NS}.pipeline_opportunity_metrics
WHERE `Product Line` = 'Northwind Commercial Card' AND `Stage` = 'Closed Lost'
GROUP BY ALL ORDER BY lost_deals DESC;"""),
            q("How did inbound demand change after the launch?", f"""SELECT `Created Date`, MEASURE(`Leads`) AS leads
FROM {NS}.demand_inbound_lead_metrics
WHERE `Created Date` >= DATE'2026-09-21'
GROUP BY ALL ORDER BY `Created Date`;"""),
        ],
        "benchmarks": [
            (["Where do Northwind Commercial Card deals stall in the funnel?", "Which stage do deals spend the most time in?", "Where is the funnel slowest?"],
             f"""SELECT `Stage`, MEASURE(`Average Days In Stage`) AS avg_days, MEASURE(`Stall Rate`) AS stall_rate FROM {NS}.funnel_stage_metrics WHERE `Product Line` = 'Northwind Commercial Card' GROUP BY ALL ORDER BY avg_days DESC;"""),
            (["What's driving the Solution-stage stall?", "Why do deals stall in Solution?", "Is the Solution stall a NetSuite problem?"],
             f"""SELECT `ERP System`, MEASURE(`Average Days In Stage`) AS avg_days, MEASURE(`Stalled Opportunities`) AS stalled FROM {NS}.funnel_stage_metrics WHERE `Product Line` = 'Northwind Commercial Card' AND `Stage` = 'Solution' GROUP BY ALL ORDER BY avg_days DESC;"""),
            (["Which open Northwind Commercial Card deals are stalled right now?", "Show me stalled open pipeline"],
             f"""SELECT `Opportunity ID`, `Account Name`, `Stage`, MEASURE(`Max Days In Stage`) AS days_in_stage FROM {NS}.funnel_stage_metrics WHERE `Product Line` = 'Northwind Commercial Card' AND `Is Stalled` = true AND `Is Current Stage` = true GROUP BY ALL ORDER BY days_in_stage DESC;"""),
            (["Why did OPP-01042 close lost?", "What happened with opportunity OPP-01042?", "Tell me about the Riverbendstone Distribution deal"],
             f"""SELECT `Opportunity ID`, `Account Name`, `ERP System`, `Lead Source`, `Stage`, `Close Reason`, MEASURE(`Lost Volume`) AS lost_volume FROM {NS}.pipeline_opportunity_metrics WHERE `Opportunity ID` = 'OPP-01042' GROUP BY ALL;"""),
            (["Why are we losing Northwind Commercial Card deals?", "Top loss reasons for Northwind Commercial Card", "What's the number one close-lost reason for Northwind Commercial Card?"],
             f"""SELECT `Close Reason`, MEASURE(`Lost Opportunities`) AS lost_deals, MEASURE(`Lost Volume`) AS lost_volume FROM {NS}.pipeline_opportunity_metrics WHERE `Product Line` = 'Northwind Commercial Card' AND `Stage` = 'Closed Lost' GROUP BY ALL ORDER BY lost_deals DESC;"""),
            (["Which ERP systems lose most to the integration gap?", "Is the ERP gap a NetSuite problem?"],
             f"""SELECT `ERP System`, MEASURE(`Lost Opportunities`) AS erp_gap_losses, MEASURE(`Lost Volume`) AS lost_volume FROM {NS}.pipeline_opportunity_metrics WHERE `Product Line` = 'Northwind Commercial Card' AND `Close Reason` = 'ERP integration gap' GROUP BY ALL ORDER BY erp_gap_losses DESC;"""),
            (["Which lead sources win most often?", "Win rate by lead source", "Is partner-sourced pipeline converting?"],
             f"""SELECT `Lead Source`, MEASURE(`Win Rate`) AS win_rate FROM {NS}.pipeline_opportunity_metrics GROUP BY ALL ORDER BY win_rate DESC;"""),
            (["How did inbound demand change after launch?", "How many leads did we get on launch day?", "Did the 9/30 launch spike demand?"],
             f"""SELECT `Created Date`, MEASURE(`Leads`) AS leads FROM {NS}.demand_inbound_lead_metrics WHERE `Created Date` >= DATE'2026-09-21' GROUP BY ALL ORDER BY `Created Date`;"""),
            (["Which campaigns drive pipeline, not just engagement?", "Compare the Launch Webinar and the CFO Roundtable"],
             f"""SELECT `Campaign`, MEASURE(`Responses`) AS responses, MEASURE(`Pipeline per Response`) AS pipeline_per_response FROM {NS}.marketing_campaign_metrics GROUP BY ALL ORDER BY responses DESC;"""),
            (["What do prospects talk about on lost deals?", "Top call themes in lost Northwind Commercial Card deals"],
             f"""SELECT `Theme`, MEASURE(`Calls on Lost Deals`) AS lost_calls FROM {NS}.signal_sales_call_metrics WHERE `Product Line` = 'Northwind Commercial Card' GROUP BY ALL ORDER BY lost_calls DESC;"""),
            (["If we closed the ERP integration gap, how much lost Northwind Commercial Card pipeline could we recover?", "What is the ERP gap worth for Northwind Commercial Card?"],
             f"""SELECT MEASURE(`Lost Volume`) AS erp_lost_volume, MEASURE(`Lost Opportunities`) AS erp_lost_opps FROM {NS}.pipeline_opportunity_metrics WHERE `Product Line` = 'Northwind Commercial Card' AND `Close Reason` = 'ERP integration gap';"""),
            (["What's our open Northwind Commercial Card pipeline and win rate?", "How big is the Northwind Commercial Card pipeline?"],
             f"""SELECT MEASURE(`Open Pipeline Volume`) AS open_pipeline, MEASURE(`Win Rate`) AS win_rate FROM {NS}.pipeline_opportunity_metrics WHERE `Product Line` = 'Northwind Commercial Card';"""),
        ],
        "sample_questions": ["Where do Northwind Commercial Card deals stall in the funnel?",
                             "What's driving the Solution-stage stall?",
                             "Why did OPP-01042 close lost?", "Why are we losing Northwind Commercial Card deals?",
                             "How did inbound demand change after the 9/30 launch?",
                             "Which campaigns drive pipeline, not just engagement?"],
    },
]


def new_id():
    return uuid.uuid4().hex


def build(agent):
    tables = []
    for v in sorted(agent["views"]):
        cols = sorted(c["name"] for c in api("get", f"/api/2.1/unity-catalog/tables/{NS}.{v}")[0].get("columns", []))
        cfg = []
        for c in cols:
            entry = {"column_name": c}
            if c in ENTITY_MATCH:
                entry.update({"enable_format_assistance": True, "enable_entity_matching": True})
            cfg.append(entry)
        tables.append({"identifier": f"{NS}.{v}", "column_configs": cfg})
    instr = {
        "text_instructions": [{"id": new_id(), "content": [l + "\n" for l in agent["instructions"][:-1]] + [agent["instructions"][-1]]}],
        "example_question_sqls": sorted([{"id": new_id(), "question": [e["question"]], "sql": sql_lines(e["sql"])}
                                         for e in agent["examples"]], key=lambda x: x["id"]),
    }
    bench = []
    for phrasings, sql in agent["benchmarks"]:
        for p in phrasings:
            bench.append({"id": new_id(), "question": [p], "answer": [{"format": "SQL", "content": sql_lines(sql)}]})
    space = {
        "version": 2,
        "config": {"sample_questions": sorted([{"id": new_id(), "question": [s]} for s in agent["sample_questions"]],
                                              key=lambda x: x["id"])},
        "data_sources": {"tables": tables, "volumes": [{"path": f"{VOL}/{v}/"} for v in sorted(agent["volumes"])]},
        "instructions": instr,
        "benchmarks": {"questions": sorted(bench, key=lambda x: x["id"])},
    }
    return space


def api(method, path, body=None):
    cmd = ["databricks", "api", method, path, "--profile", PROFILE]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout or "{}"), r.stderr
    except json.JSONDecodeError:
        return {}, r.stdout + r.stderr


def main():
    dry = "--dry-run" in sys.argv
    existing = {s["title"]: s["space_id"] for s in api("get", "/api/2.0/genie/spaces")[0].get("spaces", [])}
    ids = {}
    for agent in AGENTS:
        space = build(agent)
        body = {"warehouse_id": WAREHOUSE, "title": agent["title"], "description": agent["description"],
                "parent_path": PARENT, "serialized_space": json.dumps(space)}
        if dry:
            print(json.dumps(space, indent=1)[:2000])
            continue
        sid = existing.get(agent["title"])
        res, err = api("patch", f"/api/2.0/genie/spaces/{sid}", body) if sid else api("post", "/api/2.0/genie/spaces", body)
        if res.get("space_id"):
            ids[agent["title"]] = res["space_id"]
            print(f"{'updated' if sid else 'created'} {agent['title']}: {res['space_id']}")
        else:
            print(f"{agent['title']} failed: {err.strip()[:400]}")
            sys.exit(1)
    if not dry:   # consumed by rebuild.sh -> app bundle variables
        json.dump(ids, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".genie_ids.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
