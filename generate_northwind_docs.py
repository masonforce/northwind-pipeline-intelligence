#!/usr/bin/env python3
"""
Generate the Pipeline Intelligence demo's unstructured documents: Outreach call transcripts,
one PDF per call, from the records written by generate_northwind_data.py.

Each transcript is ENTITY-KEYED: its Call ID (CALL-) is in the filename, and the header block
lists its Opportunity ID (OPP-) and Account ID (ACCT-). Genie / the northwind_documents function joins
the ID in a question to both the transcript and the metric views, so "why did OPP-01042 stall or
close lost?" blends the number (metric views) with the driver (the prospect's own words).

Volume (./docs/call_transcripts/): one PDF per call, plus a manifest.json mapping file -> IDs.

Run generate_northwind_data.py first. SYNTHETIC content. Standard library only.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pdf_writer import make_pdf  # noqa: E402  (dependency-free PDF writer, local module)

LANDING = os.path.join(HERE, "landing")
DOCS = os.path.join(HERE, "docs")


def read_csv(*parts):
    with open(os.path.join(LANDING, *parts)) as f:
        return list(csv.DictReader(f))


def write_pdf(folder, filename, title, sections, metadata, manifest, ids):
    path = os.path.join(DOCS, folder)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, filename), "wb") as f:
        f.write(make_pdf(title, sections, metadata))
    manifest.append({"filename": filename, "title": title, **ids})


def main():
    accounts = {a["account_id"]: a for a in read_csv("salesforce", "accounts.csv")}
    opps = {o["opportunity_id"]: o for o in read_csv("salesforce", "opportunities.csv")}
    with open(os.path.join(LANDING, "outreach", "calls.jsonl")) as f:
        calls = [json.loads(line) for line in f]

    # ---------------------------------------------------------------- call transcripts
    man = []
    for c in calls:
        o, a = opps[c["opportunity_id"]], accounts[c["account_id"]]
        meta = {"Call ID": c["call_id"], "Opportunity ID": o["opportunity_id"], "Account ID": a["account_id"],
                "Account": a["account_name"], "Date": c["call_date"], "Rep": c["rep"],
                "Duration": f"{int(c['duration_sec']) // 60} min", "Source": "Outreach call recording (transcribed)"}
        write_pdf("call_transcripts", f"{c['call_id']}.pdf",
                  f"Call Transcript {c['call_id']} ({o['opportunity_id']})",
                  [("Transcript", c["transcript"])], meta, man,
                  {"call_id": c["call_id"], "opportunity_id": o["opportunity_id"],
                   "account_id": a["account_id"], "date": c["call_date"]})
    json.dump(man, open(os.path.join(DOCS, "call_transcripts", "manifest.json"), "w"), indent=1)

    print("call_transcripts", len(os.listdir(os.path.join(DOCS, "call_transcripts"))) - 1, "files")


if __name__ == "__main__":
    main()
