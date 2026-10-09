#!/usr/bin/env python3
"""
Generate synthetic "source-system drops" for the Northwind (Northwind Commercial Card) Pipeline Intelligence demo.

Writes the raw Salesforce, marketing and Outreach records the demo needs. These feed two things:
  1. generate_sfdc_connector_tables.py reshapes the Salesforce + marketing records into the
     tables the Lakeflow Connect Salesforce connector would write (landing_sfdc/), which the
     pipeline then ingests. That is the governed path for this demo.
  2. generate_northwind_docs.py turns the Outreach calls into entity-keyed transcript PDFs.

This is the pipeline-only subset of the broader commercial-loop generator: Salesforce pipeline,
marketing campaigns and Outreach calls. The Bill Pay beta, product telemetry and launch-readiness
trackers are intentionally out of scope for the narrowed Pipeline Intelligence use case.

Every record carries a consistent ID (ACCT-, LEAD-, OPP-, CMP-, CALL-) that is also stamped into
the transcript documents, so a question about a specific record joins to both the metrics and the
transcript ("why did OPP-01042 close lost?").

Planted findings (verify.sql checks them after the pipeline runs):
  1. ERP integration gap is the #1 close-lost reason for Northwind Commercial Card, worst on NetSuite.
  2. Partner-sourced opportunities have the lowest win rate; Referral the highest.
  3. Inbound leads spike 5-6x on the 9/30/2026 launch day and 10/1.
  4. Launch Webinar = most responses, little pipeline; CFO Roundtable = few responses, most pipeline per response.
  5. ERP-gap losses and NetSuite deals stall in the Solution stage (planted in OpportunityHistory,
     generate_sfdc_connector_tables.py) - the funnel-stall signal.
  Anchors: OPP-01042 (lost to ERP gap, NetSuite, Partner-sourced), ACCT-0317 (NetSuite mid-market).

All content is SYNTHETIC. Standard library only. Deterministic (seed=42).
Output: ./landing/... (read by generate_sfdc_connector_tables.py) and ./ground_truth/ (local only).
"""

import csv
import json
import os
import random
from datetime import date, timedelta

random.seed(42)
HERE = os.path.dirname(os.path.abspath(__file__))
LANDING = os.path.join(HERE, "landing")
TRUTH = os.path.join(HERE, "ground_truth")

AS_OF = date(2026, 10, 1)            # last day of data
HISTORY_START = date(2025, 10, 1)
EARLY_ACCESS = date(2026, 4, 1)      # Northwind Commercial Card early-access waitlist opens
BETA_START = date(2026, 7, 1)        # Bill Pay beta starts (still shapes the lead/product mix)
LAUNCH = date(2026, 9, 30)           # Northwind Commercial Card GA

# ---------------------------------------------------------------------------- reference
INDUSTRIES = ["Professional Services", "Manufacturing", "Healthcare", "Technology",
              "Construction", "Wholesale & Distribution", "Retail"]
REVENUE_BANDS = [("$10M-$50M", 0.40), ("$50M-$250M", 0.40), ("$250M-$1B", 0.20)]
ERPS = [("NetSuite", 0.30), ("QuickBooks Online", 0.25), ("Sage Intacct", 0.15),
        ("Microsoft Dynamics 365", 0.15), ("SAP Business One", 0.10), ("Other", 0.05)]
STATES = ["NY", "CA", "TX", "FL", "IL", "GA", "NJ", "MA", "WA", "CO", "NC", "AZ", "OH", "PA"]
NAME_A = ["North", "Blue", "Granite", "Summit", "Cedar", "Harbor", "Iron", "Silver", "Prairie",
          "Copper", "Lakeside", "Redwood", "Beacon", "Atlas", "Meridian", "Pioneer", "Keystone",
          "Riverbend", "Oakline", "Westgate", "Bright", "Clearwater", "Highland", "Union"]
NAME_B = ["field", "stone", "ridge", "point", "works", "bridge", "line", "path", "crest", "gate"]
NAME_C = ["Logistics", "Health Partners", "Engineering", "Systems", "Builders", "Supply Co",
          "Consulting Group", "Manufacturing", "Labs", "Distribution", "Advisors", "Industries"]

SOURCES = [("Inbound Web", 0.35), ("Paid Search", 0.15), ("Partner", 0.15),
           ("Referral", 0.10), ("Event", 0.10), ("Outbound", 0.15)]
LEAD_CONVERT = {"Referral": 0.40, "Event": 0.30, "Inbound Web": 0.25,
                "Partner": 0.24, "Paid Search": 0.18, "Outbound": 0.15}
WIN_RATE = {"Referral": 0.40, "Event": 0.31, "Inbound Web": 0.28,
            "Outbound": 0.21, "Paid Search": 0.22, "Partner": 0.15}

# Raw product strings are deliberately messy; the pipeline normalizes them.
PRODUCT_RAW = {
    "Northwind Commercial Card": ["Northwind Commercial Card", "northwind corporate", "Corporate Platform",
                       "Northwind Corp - Expense Mgmt", "Northwind Commercial Card (Web)"],
    "Bill Pay": ["Bill Pay", "AP Automation", "bill pay beta", "Accounts Payable"],
    "Other Northwind Products": ["Business Platinum Card", "Business Gold Card",
                                     "Corporate Card (Legacy)", "Card - unspecified"],
}

LOST_REASONS_CORP = [("ERP integration gap", 0.36), ("Chose competitor", 0.22),
                     ("Pricing / rewards", 0.17), ("Timing", 0.13), ("No decision", 0.12)]
LOST_REASONS_OTHER = [("Pricing / rewards", 0.34), ("Chose competitor", 0.22),
                      ("Timing", 0.20), ("No decision", 0.18), ("ERP integration gap", 0.06)]
COMPETITORS = [("Ramp", 0.38), ("Brex", 0.27), ("Navan", 0.20), ("Bill.com", 0.15)]

CAMPAIGNS = [
    # id, name, channel, start, spend, response_weight, lead_rate, quality
    ("CMP-01", "Northwind Commercial Card Launch Webinar", "Webinar", date(2026, 9, 15), 85000, 9.0, 0.05, 0.6),
    ("CMP-02", "CFO Roundtable Series", "Event", date(2026, 5, 1), 140000, 0.8, 0.55, 2.4),
    ("CMP-03", "Paid Search - Expense Management", "Paid Search", date(2026, 4, 1), 220000, 4.0, 0.10, 0.9),
    ("CMP-04", "Paid Search - AP Automation", "Paid Search", date(2026, 7, 1), 90000, 2.0, 0.10, 0.9),
    ("CMP-05", "NetSuite Partner Co-Marketing", "Partner", date(2026, 4, 15), 60000, 1.2, 0.30, 1.0),
    ("CMP-06", "Middle Market Summit 2026", "Event", date(2026, 6, 10), 175000, 1.5, 0.35, 1.6),
    ("CMP-07", "Bill Pay Beta Invite", "Email", date(2026, 6, 15), 15000, 1.8, 0.20, 1.2),
    ("CMP-08", "Email Nurture - Corporate Card Upgrade", "Email", date(2025, 11, 1), 25000, 3.0, 0.06, 0.7),
    ("CMP-09", "LinkedIn - Spend Control", "Paid Social", date(2026, 8, 1), 70000, 2.5, 0.08, 0.8),
    ("CMP-10", "Referral Program Q3", "Referral", date(2026, 7, 1), 30000, 0.7, 0.45, 1.8),
]
SOURCE_CAMPAIGNS = {"Paid Search": ["CMP-03", "CMP-04", "CMP-09"], "Event": ["CMP-02", "CMP-06"],
                    "Inbound Web": ["CMP-01", "CMP-07", "CMP-08"], "Partner": ["CMP-05"],
                    "Referral": ["CMP-10"], "Outbound": []}

REPS = ["Dana Whitfield", "Marcus Lee", "Priya Raman", "Tom Okafor", "Elena Ruiz", "Sam Patel",
        "Jordan Brooks", "Mia Chen"]
FIRST = ["Alex", "Jamie", "Chris", "Taylor", "Morgan", "Pat", "Robin", "Casey", "Drew", "Lee"]


def wpick(pairs):
    r, acc = random.random(), 0.0
    for v, w in pairs:
        acc += w
        if r <= acc:
            return v
    return pairs[-1][0]


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def write_csv(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------- accounts
def gen_accounts(n=600):
    used, rows = set(), []
    for i in range(1, n + 1):
        while True:
            name = f"{random.choice(NAME_A)}{random.choice(NAME_B)} {random.choice(NAME_C)}"
            if name not in used:
                used.add(name)
                break
        band = wpick(REVENUE_BANDS)
        emp = {"$10M-$50M": (50, 250), "$50M-$250M": (200, 1200), "$250M-$1B": (900, 4500)}[band]
        rows.append({
            "account_id": f"ACCT-{i:04d}", "account_name": name,
            "industry": random.choice(INDUSTRIES), "revenue_band": band,
            "employee_count": random.randint(*emp), "hq_state": random.choice(STATES),
            "erp_system": wpick(ERPS),
            "existing_northwind_customer": str(random.random() < 0.55).lower(),
            "bill_pay_beta": "false",
        })
    # Anchor ACCT-0317: NetSuite mid-market
    a = rows[316]
    a.update({"account_name": "Harborline Engineering", "revenue_band": "$50M-$250M",
              "erp_system": "NetSuite", "industry": "Manufacturing", "existing_northwind_customer": "true"})
    return rows


# ---------------------------------------------------------------------------- leads
def daily_lead_volume(d):
    base = 7 + 6 * (d - HISTORY_START).days / 365          # grows ~7 -> 13/day
    if d >= EARLY_ACCESS:
        base += 3
    if d == LAUNCH:
        base *= 6
    elif d == AS_OF:
        base *= 5
    if d.weekday() >= 5:
        base *= 0.35
    return max(0, int(random.gauss(base, base * 0.15)))


def product_mix(d):
    if d < EARLY_ACCESS:
        return [("Other Northwind Products", 1.0)]
    if d < BETA_START:
        return [("Northwind Commercial Card", 0.55), ("Other Northwind Products", 0.45)]
    if d >= LAUNCH:
        return [("Northwind Commercial Card", 0.72), ("Bill Pay", 0.08), ("Other Northwind Products", 0.20)]
    return [("Northwind Commercial Card", 0.60), ("Bill Pay", 0.07), ("Other Northwind Products", 0.33)]


def gen_leads(accounts):
    rows, n = [], 0
    for d in daterange(HISTORY_START, AS_OF):
        for _ in range(daily_lead_volume(d)):
            n += 1
            src = wpick(SOURCES)
            line = wpick(product_mix(d))
            camps = [c for c in SOURCE_CAMPAIGNS[src]
                     if next(x for x in CAMPAIGNS if x[0] == c)[3] <= d]
            camp = random.choice(camps) if camps and random.random() < 0.7 else ""
            if d in (LAUNCH, AS_OF) and src == "Inbound Web" and random.random() < 0.6:
                camp = "CMP-01"
            age = (AS_OF - d).days
            if age < 14:
                status = "Open"
            else:
                status = "Converted" if random.random() < LEAD_CONVERT[src] else \
                    random.choice(["Disqualified", "Disqualified", "Nurture"])
            rows.append({
                "lead_id": f"LEAD-{n:05d}", "account_id": random.choice(accounts)["account_id"],
                "created_date": d.isoformat(), "lead_source": src,
                "product_interest_raw": random.choice(PRODUCT_RAW[line]),
                "campaign_id": camp, "lead_status": status,
                "_line": line,
            })
    return rows


# ---------------------------------------------------------------------------- opportunities
def gen_opportunities(leads, accounts):
    acct = {a["account_id"]: a for a in accounts}
    rows, n = [], 1000
    for ld in leads:
        if ld["lead_status"] != "Converted":
            continue
        n += 1
        a = acct[ld["account_id"]]
        created = date.fromisoformat(ld["created_date"]) + timedelta(days=random.randint(3, 12))
        line = ld["_line"]
        lo, hi = {"$10M-$50M": (0.4, 3), "$50M-$250M": (2, 12), "$250M-$1B": (8, 40)}[a["revenue_band"]]
        volume = round(random.uniform(lo, hi) * 1_000_000, -3)
        cycle = random.randint(35, 110)
        close = created + timedelta(days=cycle)
        win_p = WIN_RATE[ld["lead_source"]]
        if line == "Northwind Commercial Card" and a["erp_system"] == "NetSuite":
            win_p *= 0.75
        reason, competitor = "", ""
        if close <= AS_OF:
            won = random.random() < win_p
            stage = "Closed Won" if won else "Closed Lost"
            if not won:
                reasons = LOST_REASONS_CORP if line in ("Northwind Commercial Card", "Bill Pay") else LOST_REASONS_OTHER
                if line == "Northwind Commercial Card" and a["erp_system"] == "NetSuite":
                    reasons = [("ERP integration gap", 0.55)] + [(r, w * 0.7) for r, w in reasons[1:]]
                reason = wpick(reasons)
                if reason == "Chose competitor":
                    competitor = wpick(COMPETITORS)
        else:
            stage = random.choice(["Discovery", "Discovery", "Solution", "Proposal", "Negotiation"])
            close = max(close, AS_OF + timedelta(days=random.randint(7, 75)))
        rows.append({
            "opportunity_id": f"OPP-{n:05d}", "account_id": a["account_id"], "lead_id": ld["lead_id"],
            "product_interest_raw": ld["product_interest_raw"], "lead_source": ld["lead_source"],
            "campaign_id": ld["campaign_id"], "owner": random.choice(REPS),
            "created_date": created.isoformat(), "close_date": close.isoformat(), "stage": stage,
            "projected_annual_volume": int(volume), "close_reason": reason, "competitor": competitor,
            "_line": line,
        })
    # Anchor OPP-01042: Northwind Commercial Card, NetSuite account, Partner-sourced, lost to ERP gap
    o = next(r for r in rows if r["opportunity_id"] == "OPP-01042")
    netsuite = next(a for a in accounts if a["erp_system"] == "NetSuite" and a["revenue_band"] == "$50M-$250M"
                    and a["account_id"] != "ACCT-0317")
    o.update({"account_id": netsuite["account_id"], "product_interest_raw": "Northwind Commercial Card",
              "_line": "Northwind Commercial Card", "lead_source": "Partner", "campaign_id": "CMP-05",
              "created_date": "2026-05-04", "close_date": "2026-08-21", "stage": "Closed Lost",
              "projected_annual_volume": 9_400_000, "close_reason": "ERP integration gap",
              "competitor": "", "owner": "Priya Raman"})
    ld = next(l for l in leads if l["lead_id"] == o["lead_id"])     # keep the source lead consistent
    ld.update({"account_id": netsuite["account_id"], "created_date": "2026-04-27", "lead_source": "Partner",
               "product_interest_raw": "Northwind Commercial Card", "campaign_id": "CMP-05", "_line": "Northwind Commercial Card"})
    return rows


# ---------------------------------------------------------------------------- campaign responses
def gen_campaign_responses(accounts, leads, opps):
    lead_by_camp = {}
    for ld in leads:
        if ld["campaign_id"]:
            lead_by_camp.setdefault(ld["campaign_id"], []).append(ld)
    rows, n = [], 0
    for cid, name, ch, start, spend, weight, lead_rate, q in CAMPAIGNS:
        end = min(AS_OF, start + timedelta(days=150))
        total = int(weight * 120)
        camp_leads = lead_by_camp.get(cid, [])
        for i in range(total):
            n += 1
            d = start + timedelta(days=random.randint(0, max(0, (end - start).days)))
            ld = camp_leads[i] if i < len(camp_leads) else None
            rows.append({
                "response_id": f"RESP-{n:06d}", "campaign_id": cid, "response_date": d.isoformat(),
                "account_id": ld["account_id"] if ld else random.choice(accounts)["account_id"],
                "response_type": random.choice(["Registered", "Attended", "Clicked", "Downloaded"]),
                "lead_id": ld["lead_id"] if ld else "",
            })
    camps = [{"campaign_id": c[0], "campaign_name": c[1], "channel": c[2],
              "start_date": c[3].isoformat(), "budget_usd": c[4]} for c in CAMPAIGNS]
    return camps, rows


# ---------------------------------------------------------------------------- calls (Outreach)
THEMES = {
    "ERP integration": [
        "Our finance team lives in {erp}. If card transactions and receipts don't sync into {erp} automatically, my controller will say no.",
        "We tried another tool last year and the {erp} sync broke every month-end close. That is the first thing I need to see working.",
        "Can you post coded transactions straight to our {erp} general ledger, or is it a CSV export?",
    ],
    "Approval workflows": [
        "We need multi-level approvals. Anything over twenty-five thousand has to go to the CFO, and it should route by department and GL code.",
        "Our auditors flagged that approvers could approve their own requests at our last provider. How do you handle delegation and segregation of duties?",
    ],
    "Vendor card acceptance": [
        "About a third of our vendors don't take cards today. What happens to those payments?",
        "If our suppliers won't accept Northwind we can't move the spend over, so vendor acceptance is a real question.",
    ],
    "Pricing & rewards": [
        "Ramp is offering us a higher cashback rate. What does the rebate look like at our volume?",
        "The rewards are attractive, but I need to understand the fee structure for international spend.",
    ],
    "Onboarding & implementation": [
        "How long does implementation take? We can't have a three-month rollout with our team size.",
        "Who supports us during setup? Last time we were handed a help center link and left alone.",
    ],
    "Bill Pay interest": [
        "If you add accounts payable, I'd consolidate our bill payments onto the same platform as our cards.",
        "Is the Bill Pay product available yet? Paying vendors from one place is the reason we're talking to you.",
    ],
    "Expense policy controls": [
        "I want spend limits by role and merchant category set before cards go out.",
        "Can the policy block out-of-policy spend in real time instead of flagging it after the fact?",
    ],
}
REP_LINES = [
    "Thanks for making time today. I'd like to understand how your team manages spend today.",
    "That's helpful. Let me show you how Northwind Commercial Card handles that.",
    "Understood. I'll follow up with our solutions team on that point.",
    "Let me recap the next steps and send a summary after the call.",
]


def gen_calls(opps, accounts):
    acct = {a["account_id"]: a for a in accounts}
    targets = [o for o in opps if o["_line"] in ("Northwind Commercial Card", "Bill Pay")]
    random.shuffle(targets)
    chosen = targets[:150]
    if not any(o["opportunity_id"] == "OPP-01042" for o in chosen):
        chosen.append(next(o for o in opps if o["opportunity_id"] == "OPP-01042"))
    rows, truth, n = [], [], 0
    for o in sorted(chosen, key=lambda x: x["opportunity_id"]):
        a = acct[o["account_id"]]
        k = 3 if o["opportunity_id"] == "OPP-01042" else random.choice([1, 1, 2, 2, 3])
        for j in range(k):
            n += 1
            if o["close_reason"] == "ERP integration gap" or (a["erp_system"] == "NetSuite" and random.random() < 0.5):
                primary = "ERP integration"
            elif o["close_reason"] == "Pricing / rewards" or (o["competitor"] and random.random() < 0.4):
                primary = "Pricing & rewards"
            elif o["competitor"]:
                primary = random.choice(["Onboarding & implementation", "Expense policy controls",
                                         "Approval workflows", "Vendor card acceptance"])
            elif o["_line"] == "Bill Pay":
                primary = random.choice(["Bill Pay interest", "Approval workflows", "Vendor card acceptance"])
            else:
                primary = random.choice(list(THEMES))
            secondary = random.choice([t for t in THEMES if t != primary])
            cdate = date.fromisoformat(o["created_date"]) + timedelta(days=7 + 14 * j)
            cdate = min(cdate, AS_OF)
            prospect = random.choice(FIRST)
            lines = [f"{o['owner']} (Northwind): {REP_LINES[0]}",
                     f"{prospect} ({a['account_name']}): {random.choice(THEMES[primary]).format(erp=a['erp_system'])}",
                     f"{o['owner']} (Northwind): {REP_LINES[1]}",
                     f"{prospect} ({a['account_name']}): {random.choice(THEMES[primary]).format(erp=a['erp_system'])}",
                     f"{prospect} ({a['account_name']}): {random.choice(THEMES[secondary]).format(erp=a['erp_system'])}"]
            if o["competitor"]:
                lines.append(f"{prospect} ({a['account_name']}): To be transparent, we are also evaluating {o['competitor']}.")
            lines += [f"{o['owner']} (Northwind): {REP_LINES[2]}", f"{o['owner']} (Northwind): {REP_LINES[3]}"]
            if o["opportunity_id"] == "OPP-01042" and j == 2:
                lines = [f"{o['owner']} (Northwind): Thanks for the candid feedback on the decision.",
                         f"{prospect} ({a['account_name']}): We liked the card program and the rewards, but our controller "
                         f"would not sign off without a native NetSuite sync. Exporting CSVs into NetSuite every week is a non-starter for our close.",
                         f"{prospect} ({a['account_name']}): If ERP Sync ships, call us. We would revisit in Q1.",
                         f"{o['owner']} (Northwind): Understood. I'll make sure product hears this directly."]
                primary, secondary = "ERP integration", "Pricing & rewards"
                cdate = date(2026, 8, 24)                      # loss debrief, after the 8/21 close
            call_id = f"CALL-{n:04d}"
            rows.append({"call_id": call_id, "opportunity_id": o["opportunity_id"], "account_id": a["account_id"],
                         "call_date": cdate.isoformat(), "rep": o["owner"],
                         "duration_sec": random.randint(900, 2700), "transcript": "\n".join(lines)})
            truth.append({"call_id": call_id, "primary_theme": primary, "secondary_theme": secondary})
    return rows, truth


# ---------------------------------------------------------------------------- main
def main():
    accounts = gen_accounts()
    leads = gen_leads(accounts)
    opps = gen_opportunities(leads, accounts)
    camps, responses = gen_campaign_responses(accounts, leads, opps)
    calls, call_truth = gen_calls(opps, accounts)

    strip = lambda rows: [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    sf = os.path.join(LANDING, "salesforce")
    write_csv(os.path.join(sf, "accounts.csv"), accounts, list(accounts[0]))
    write_csv(os.path.join(sf, "leads.csv"), strip(leads), [k for k in leads[0] if not k.startswith("_")])
    write_csv(os.path.join(sf, "opportunities.csv"), strip(opps), [k for k in opps[0] if not k.startswith("_")])
    write_csv(os.path.join(LANDING, "marketing", "campaigns.csv"), camps, list(camps[0]))
    write_csv(os.path.join(LANDING, "marketing", "campaign_responses.csv"), responses, list(responses[0]))
    os.makedirs(os.path.join(LANDING, "outreach"), exist_ok=True)
    with open(os.path.join(LANDING, "outreach", "calls.jsonl"), "w") as f:
        for c in calls:
            f.write(json.dumps(c) + "\n")
    write_csv(os.path.join(TRUTH, "call_themes.csv"), call_truth, list(call_truth[0]))
    write_csv(os.path.join(TRUTH, "lead_product_line.csv"),
              [{"lead_id": l["lead_id"], "product_line": l["_line"]} for l in leads], ["lead_id", "product_line"])

    print(f"accounts={len(accounts)} leads={len(leads)} opps={len(opps)} calls={len(calls)} "
          f"responses={len(responses)}")


if __name__ == "__main__":
    main()
