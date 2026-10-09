#!/usr/bin/env python3
"""
Mock what the Lakeflow Connect Salesforce connector writes, from the synthetic records
generate_northwind_data.py produces. In this demo the connector output is the GOVERNED SOURCE:
the Lakeflow pipeline (pipeline/) ingests these tables directly, so the demo tells the real
pilot story (Salesforce -> Lakeflow Connect -> Unity Catalog), including stage history.

The connector writes one table per Salesforce object into the destination schema, with
Salesforce API field names, 18-character record IDs, and SystemModstamp / LastModifiedDate
cursor columns (SCD type 1 by default, so soft-deleted rows are simply absent). This script
writes those shapes as CSVs under ./landing_sfdc/<object>.csv; rebuild.sh uploads them to the
`landing_sfdc` volume and the pipeline's bronze layer reads them from there.

OpportunityHistory (stage changes over time) carries the planted funnel stall: ERP-gap losses
and NetSuite deals linger in "Solution" (technical validation). This is what the Pipeline
Intelligence agent and the funnel_stage_metrics view surface.

Readable demo keys (OPP-01042, ACCT-0317, LEAD-00151, CMP-01) are kept in custom fields
(Northwind_*_Key__c) so documents and Genie questions keep working. Standard library, seed 7.
"""

import csv
import hashlib
import os
import random
from datetime import date, datetime, timedelta

random.seed(7)
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "landing", "salesforce")
SRC_MKT = os.path.join(HERE, "landing", "marketing")
OUT = os.path.join(HERE, "landing_sfdc")
B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
STAGES = ["Discovery", "Solution", "Proposal", "Negotiation"]
PROB = {"Discovery": 10, "Solution": 30, "Proposal": 60, "Negotiation": 80, "Closed Won": 100, "Closed Lost": 0}
FORECAST = {"Discovery": "Pipeline", "Solution": "Pipeline", "Proposal": "Best Case", "Negotiation": "Commit",
            "Closed Won": "Closed", "Closed Lost": "Omitted"}


def sf_id(prefix: str, key: str) -> str:
    """Deterministic Salesforce-style 18-char ID: 3-char key prefix + 12 base62 chars + checksum."""
    h = int(hashlib.sha1(key.encode()).hexdigest(), 16)
    body = prefix + "".join(B62[(h >> (6 * i)) % 62] for i in range(12))
    suffix = ""
    for chunk in (body[0:5], body[5:10], body[10:15]):
        bits = sum(1 << i for i, ch in enumerate(chunk) if ch.isupper())
        suffix += "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"[bits]
    return body + suffix


def ts(d: date, hour=None) -> str:
    t = datetime(d.year, d.month, d.day, hour if hour is not None else random.randint(13, 22), random.randint(0, 59))
    return t.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def write(name, rows):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"{name}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    accts, leads, opps = read(f"{SRC}/accounts.csv"), read(f"{SRC}/leads.csv"), read(f"{SRC}/opportunities.csv")
    camps, resps = read(f"{SRC_MKT}/campaigns.csv"), read(f"{SRC_MKT}/campaign_responses.csv")
    aid = {a["account_id"]: sf_id("001", a["account_id"]) for a in accts}
    lid = {l["lead_id"]: sf_id("00Q", l["lead_id"]) for l in leads}
    oid = {o["opportunity_id"]: sf_id("006", o["opportunity_id"]) for o in opps}
    cid = {c["campaign_id"]: sf_id("701", c["campaign_id"]) for c in camps}
    owners = sorted({o["owner"] for o in opps})
    uid = {n: sf_id("005", n) for n in owners}
    acct_by = {a["account_id"]: a for a in accts}
    opp_by_lead = {o["lead_id"]: o for o in opps}
    as_of = date(2026, 10, 1)

    write("user", [{"Id": uid[n], "Name": n, "Username": n.lower().replace(" ", ".") + "@northwind.example.com",
                    "IsActive": "true", "Department": "Northwind Commercial Card Sales",
                    "SystemModstamp": ts(date(2025, 9, 1))} for n in owners])

    write("account", [{
        "Id": aid[a["account_id"]], "Name": a["account_name"], "Industry": a["industry"],
        "NumberOfEmployees": a["employee_count"], "BillingState": a["hq_state"], "BillingCountry": "United States",
        "Type": "Customer - Existing" if a["existing_northwind_customer"] == "true" else "Prospect",
        "Revenue_Band__c": a["revenue_band"], "ERP_System__c": a["erp_system"],
        "Bill_Pay_Beta__c": a["bill_pay_beta"], "Northwind_Account_Key__c": a["account_id"],
        "CreatedDate": ts(date(2025, 9, 15)), "LastModifiedDate": ts(as_of - timedelta(days=random.randint(1, 30))),
        "SystemModstamp": ts(as_of - timedelta(days=random.randint(0, 3))), "IsDeleted": "false",
    } for a in accts])

    write("campaign", [{
        "Id": cid[c["campaign_id"]], "Name": c["campaign_name"], "Type": c["channel"], "Status": "In Progress",
        "StartDate": c["start_date"], "BudgetedCost": c["budget_usd"], "IsActive": "true",
        "Northwind_Campaign_Key__c": c["campaign_id"], "SystemModstamp": ts(date.fromisoformat(c["start_date"])),
    } for c in camps])

    lead_rows = []
    for l in leads:
        o = opp_by_lead.get(l["lead_id"])
        created = date.fromisoformat(l["created_date"])
        lead_rows.append({
            "Id": lid[l["lead_id"]], "Company": acct_by[l["account_id"]]["account_name"],
            "Status": {"Converted": "Closed - Converted", "Disqualified": "Closed - Not Converted",
                       "Nurture": "Nurturing", "Open": "Open - Not Contacted"}[l["lead_status"]],
            "LeadSource": l["lead_source"], "Product_Interest__c": l["product_interest_raw"],
            "IsConverted": "true" if o else "false",
            "ConvertedOpportunityId": oid[o["opportunity_id"]] if o else "",
            "ConvertedAccountId": aid[l["account_id"]] if o else "",
            "ConvertedDate": o["created_date"] if o else "",
            # Primary campaign source (a common custom field on Lead); carries the readable CMP- key.
            "Northwind_Campaign_Key__c": l["campaign_id"],
            "Northwind_Lead_Key__c": l["lead_id"], "Northwind_Account_Key__c": l["account_id"],
            "CreatedDate": ts(created), "LastModifiedDate": ts(min(as_of, created + timedelta(days=14))),
            "SystemModstamp": ts(min(as_of, created + timedelta(days=14))), "IsDeleted": "false",
        })
    write("lead", lead_rows)

    write("campaign_member", [{
        "Id": sf_id("00v", r["response_id"]), "CampaignId": cid[r["campaign_id"]],
        "LeadId": lid.get(r["lead_id"], ""), "Status": "Responded", "HasResponded": "true",
        "FirstRespondedDate": r["response_date"], "Response_Type__c": r["response_type"],
        "Northwind_Account_Key__c": r["account_id"], "CreatedDate": ts(date.fromisoformat(r["response_date"])),
        "SystemModstamp": ts(date.fromisoformat(r["response_date"])),
    } for r in resps])

    opp_rows, hist_rows = [], []
    for o in opps:
        created, close = date.fromisoformat(o["created_date"]), date.fromisoformat(o["close_date"])
        stage, closed = o["stage"], o["stage"].startswith("Closed")
        acct = acct_by[o["account_id"]]
        # Stage path: closed deals walk the funnel and exit; lost deals die at a reason-driven stage.
        if stage == "Closed Won":
            path = STAGES[:]
        elif stage == "Closed Lost":
            last = {"ERP integration gap": "Solution", "Chose competitor": "Proposal", "Pricing / rewards": "Negotiation",
                    "Timing": "Discovery", "No decision": "Proposal"}.get(o["close_reason"], "Proposal")
            path = STAGES[:STAGES.index(last) + 1]
        else:
            path = STAGES[:STAGES.index(stage) + 1]
        end = close if closed else as_of
        span = max(len(path), (end - created).days)
        # Planted stall: ERP-gap losses and NetSuite deals spend much longer in Solution.
        weights = [1.0] * len(path)
        if "Solution" in path and (o["close_reason"] == "ERP integration gap" or acct["erp_system"] == "NetSuite"):
            weights[path.index("Solution")] = 4.0
        cuts, d = [], created
        for i, s in enumerate(path):
            cuts.append((s, d))
            d = d + timedelta(days=max(1, int(span * weights[i] / sum(weights))))
        if closed:
            cuts.append((stage, close))
        for n, (s, d) in enumerate(cuts):
            hist_rows.append({
                "Id": sf_id("008", f"{o['opportunity_id']}-{n}"), "OpportunityId": oid[o["opportunity_id"]],
                "StageName": s, "Amount": o["projected_annual_volume"], "CloseDate": o["close_date"],
                "Probability": PROB[s], "ForecastCategory": FORECAST[s],
                "CreatedDate": ts(min(d, as_of)), "SystemModstamp": ts(min(d, as_of)), "IsDeleted": "false",
            })
        opp_rows.append({
            "Id": oid[o["opportunity_id"]], "Name": f"{acct['account_name']} - {o['product_interest_raw']}",
            "AccountId": aid[o["account_id"]], "OwnerId": uid[o["owner"]], "CampaignId": cid.get(o["campaign_id"], ""),
            "StageName": stage, "Amount": o["projected_annual_volume"], "CloseDate": o["close_date"],
            "IsClosed": str(closed).lower(), "IsWon": str(stage == "Closed Won").lower(),
            "Probability": PROB[stage], "ForecastCategoryName": FORECAST[stage], "LeadSource": o["lead_source"],
            "Type": "New Business", "Product_Interest__c": o["product_interest_raw"],
            "Projected_Annual_Volume__c": o["projected_annual_volume"], "Loss_Reason__c": o["close_reason"],
            "Competitor__c": o["competitor"], "Northwind_Opportunity_Key__c": o["opportunity_id"],
            "Northwind_Lead_Key__c": o["lead_id"], "CreatedDate": ts(created),
            "LastModifiedDate": ts(min(end, as_of)), "SystemModstamp": ts(min(end, as_of)), "IsDeleted": "false",
        })
    write("opportunity", opp_rows)
    write("opportunity_history", hist_rows)
    print(f"user={len(owners)} account={len(accts)} lead={len(lead_rows)} opportunity={len(opp_rows)} "
          f"opportunity_history={len(hist_rows)} campaign={len(camps)} campaign_member={len(resps)}")


if __name__ == "__main__":
    main()
