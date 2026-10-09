"""
Northwind Pipeline Intelligence: one Databricks App for commercial leaders.

Tabs:
  Leader - governed commercial KPIs + a what-if on recovering ERP-gap losses
  Funnel - where deals stall: days in each stage, the Solution-stage driver, and the
           stalled open opportunities, each drilling to the prospect's own words (transcripts)
  Ask    - the Northwind Pipeline Intelligence Genie agent for metrics + a document panel that pulls
           the call transcripts for any ID mentioned (the Conversation API itself does not read volumes)

Aggregates come from the UC metric views via the SQL warehouse; transcripts come from the UC volume.
Lakebase (managed Postgres) carries the operational layer: it serves individual deal records as a
point lookup (a synced copy of the gold deal table) and takes the write-back, saved what-if scenarios
and stalled deals flagged for follow-up, so reading the stall turns into acting on it in the same
governed app. Auth is the app service principal (resources in databricks.yml).
"""

import io
import json
import os
import re

import pandas as pd
import psycopg
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from pypdf import PdfReader

WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
NS = os.environ.get("NORTHWIND_SCHEMA", "fe_demo_catalog.northwind_pipeline")
VOL = "/Volumes/" + NS.replace(".", "/")
GENIE = {"Northwind Pipeline Intelligence": os.environ.get("GENIE_PIPELINE_ID", "")}

# Lakebase (managed Postgres) holds the app's write-back state: saved what-if scenarios and
# stalled deals flagged for follow-up. The app connects as its own service principal.
PG_ENDPOINT = os.environ.get("LAKEBASE_ENDPOINT", "projects/northwind-pi/branches/production/endpoints/primary")
PG_DB = os.environ.get("PGDATABASE", "northwind")
# Individual deals are served from Lakebase too: a synced copy of the gold deal table, point-looked-up
# by opportunity_id. Aggregates stay on the lakehouse metric views; single records serve from Postgres.
DEALS_TABLE = os.environ.get("DEALS_TABLE", "northwind_pipeline.deals_online")
# Databricks-hosted foundation model that drafts a recommended next step for a stalled deal from its
# governed metrics plus the prospect's call transcript. Named model, called at runtime (see ai_next_step).
FM_ENDPOINT = os.environ.get("FM_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")

ID_PATTERN = re.compile(r"\b(OPP-\d{5}|ACCT-\d{4}|CALL-\d{4})\b")
VOLUMES = ["call_transcripts"]
STAGE_ORDER = ["Discovery", "Solution", "Proposal", "Negotiation"]


@st.cache_resource
def client() -> WorkspaceClient:
    return WorkspaceClient()


def ai_next_step(deal: dict, transcript: str) -> str:
    """Draft a recommended next step for a stalled deal with a Databricks-hosted foundation model.
    Grounds the LLM in the governed deal metrics plus the prospect's own words from the call."""
    facts = (f"Account: {deal.get('account_name')}; product: {deal.get('product_line')}; "
             f"stage: {deal.get('stage')}; days in stage: {deal.get('days_in_stage')}; "
             f"ERP system: {deal.get('erp_system')}; projected annual volume: {deal.get('projected_annual_volume')}; "
             f"close/stall reason: {deal.get('close_reason')}.")
    system = ("You are a commercial sales advisor for a corporate-card issuer. Given a stalled deal's "
              "metrics and an excerpt of the prospect's call, write a concise recommended next step "
              "(2 to 3 sentences), grounded in what the prospect actually said. No preamble.")
    user = f"Deal metrics:\n{facts}\n\nProspect call excerpt:\n{transcript[:3000]}\n\nRecommended next step:"
    resp = client().serving_endpoints.query(
        name=FM_ENDPOINT,
        messages=[ChatMessage(role=ChatMessageRole.SYSTEM, content=system),
                  ChatMessage(role=ChatMessageRole.USER, content=user)],
        max_tokens=256, temperature=0.2)
    return resp.choices[0].message.content


# ----------------------------------------------------------------------------- Lakebase (write-back)
def pg_host() -> str:
    if os.environ.get("PGHOST"):
        return os.environ["PGHOST"]
    return client().api_client.do("GET", f"/api/2.0/postgres/{PG_ENDPOINT}")["status"]["hosts"]["host"]


def pg_conn():
    """A fresh Lakebase connection as the app service principal (OAuth token, ~1h)."""
    w = client()
    token = w.api_client.do("POST", "/api/2.0/postgres/credentials", body={"endpoint": PG_ENDPOINT})["token"]
    return psycopg.connect(host=pg_host(), port=int(os.environ.get("PGPORT", 5432)), dbname=PG_DB,
                           user=os.environ.get("PGUSER") or w.config.client_id, password=token, sslmode="require")


def save_scenario(label, deals, base_volume, recovery_pct, recovered, note, user):
    with pg_conn() as conn:
        conn.execute("""INSERT INTO saved_scenarios
                        (label, driver, deals, base_volume, recovery_pct, recovered, note, saved_by)
                        VALUES (%s, 'ERP integration gap', %s, %s, %s, %s, %s, %s)""",
                     (label, deals, base_volume, recovery_pct, recovered, note, user))


def recent_scenarios(limit=5) -> pd.DataFrame:
    with pg_conn() as conn:
        rows = conn.execute("""SELECT label, recovery_pct, recovered, note, saved_by, saved_at
                               FROM saved_scenarios ORDER BY saved_at DESC LIMIT %s""", (limit,)).fetchall()
    return pd.DataFrame(rows, columns=["Scenario", "Recovery %", "Recovered volume", "Note", "Saved by", "Saved at"])


def flag_deal(opp, account, stage, days, note, owner, user):
    with pg_conn() as conn:
        conn.execute("""INSERT INTO deal_followups
                        (opportunity_id, account_name, stage, days_in_stage, note, owner, flagged_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                     (opp, account, stage, days, note, owner, user))


def recent_followups(limit=10) -> pd.DataFrame:
    with pg_conn() as conn:
        rows = conn.execute("""SELECT opportunity_id, account_name, stage, days_in_stage, status, owner, note,
                               flagged_by, flagged_at FROM deal_followups ORDER BY flagged_at DESC LIMIT %s""",
                            (limit,)).fetchall()
    return pd.DataFrame(rows, columns=["Opportunity", "Account", "Stage", "Days", "Status", "Owner", "Note",
                                       "Flagged by", "Flagged at"])


def deal_detail(opp: str) -> dict | None:
    """Point-lookup a single deal's record from the Lakebase synced table (not the warehouse)."""
    keys = ["account_name", "industry", "revenue_band", "erp_system", "product_line", "stage",
            "projected_annual_volume", "lead_source", "close_reason", "is_stalled", "days_in_stage"]
    with pg_conn() as conn:
        r = conn.execute(f"SELECT {', '.join(keys)} FROM {DEALS_TABLE} WHERE opportunity_id = %s", (opp,)).fetchone()
    return dict(zip(keys, r)) if r else None


# ----------------------------------------------------------------------------- data access
@st.cache_data(ttl=300, show_spinner=False)
def sql(query: str) -> pd.DataFrame:
    r = client().statement_execution.execute_statement(warehouse_id=WAREHOUSE_ID, statement=query, wait_timeout="50s")
    if r.status.state.value != "SUCCEEDED":
        raise RuntimeError(r.status.error.message if r.status.error else r.status.state.value)
    cols = [c.name for c in r.manifest.schema.columns]
    df = pd.DataFrame((r.result.data_array if r.result else None) or [], columns=cols)
    for c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c])
        except (ValueError, TypeError):
            pass
    return df


@st.cache_data(ttl=600, show_spinner=False)
def manifests() -> list[dict]:
    """Transcript manifests, tagged with their volume, for ID -> file lookup."""
    docs = []
    for v in VOLUMES:
        raw = client().files.download(f"{VOL}/{v}/manifest.json").contents.read()
        for m in json.loads(raw):
            docs.append({**m, "volume": v})
    return docs


@st.cache_data(ttl=600, show_spinner=False)
def pdf_text(volume: str, filename: str) -> str:
    data = client().files.download(f"{VOL}/{volume}/{filename}").contents.read()
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def docs_for(ids: set[str]) -> list[dict]:
    hits = []
    for d in manifests():
        keys = {str(v) for k, v in d.items() if k.endswith("_id")}
        if ids & keys or any(i in d["filename"] for i in ids):
            hits.append(d)
    return sorted(hits, key=lambda d: d["filename"])


def show_docs(ids: set[str], limit: int = 8) -> None:
    hits = docs_for(ids)
    if not hits:
        st.caption("No transcripts reference these IDs.")
        return
    st.caption(f"{len(hits)} transcript(s) reference {', '.join(sorted(ids))}" + (f"; showing {limit}" if len(hits) > limit else ""))
    for d in hits[:limit]:
        with st.expander(f"📄 {d['title']}  ·  {d['volume']}/{d['filename']}"):
            st.text(pdf_text(d["volume"], d["filename"]))


def current_user() -> str:
    try:
        return st.context.headers.get("X-Forwarded-Email") or "unknown@user"
    except Exception:
        return "unknown@user"


def mv(name: str) -> str:
    return f"{NS}.{name}"


# ----------------------------------------------------------------------------- tabs
def tab_leader():
    st.subheader("Northwind Commercial Card commercial engine")
    k = sql(f"""SELECT MEASURE(`Open Pipeline Volume`) open_pipe, MEASURE(`Win Rate`) win_rate, MEASURE(`Opportunities`) opps
                FROM {mv('pipeline_opportunity_metrics')} WHERE `Product Line` = 'Northwind Commercial Card'""").iloc[0]
    launch = sql(f"""SELECT `Launch Period`, MEASURE(`Average Daily Leads`) daily FROM {mv('demand_inbound_lead_metrics')}
                     WHERE `Product Line` = 'Northwind Commercial Card' GROUP BY ALL""").set_index("Launch Period")["daily"]
    erp = sql(f"""SELECT MEASURE(`Lost Volume`) v, MEASURE(`Lost Opportunities`) n FROM {mv('pipeline_opportunity_metrics')}
                  WHERE `Product Line` = 'Northwind Commercial Card' AND `Close Reason` = 'ERP integration gap'""").iloc[0]
    c = st.columns(4)
    c[0].metric("Open pipeline", f"${k.open_pipe / 1e9:.2f}B", help="Projected annual volume, open Northwind Commercial Card deals")
    c[1].metric("Win rate", f"{k.win_rate:.1f}%")
    c[2].metric("Daily leads since launch", f"{launch.get('Post-launch (GA)', 0):.0f}",
                delta=f"vs {launch.get('Early access', 0):.1f}/day in early access")
    c[3].metric("Lost to ERP gap", f"${erp.v / 1e6:.0f}M", delta=f"{int(erp.n)} deals", delta_color="inverse")

    left, right = st.columns(2)
    with left:
        st.markdown("**Why we lose Northwind Commercial Card deals**")
        lost = sql(f"""SELECT `Close Reason`, MEASURE(`Lost Volume`) / 1e6 AS lost_volume_m FROM {mv('pipeline_opportunity_metrics')}
                       WHERE `Product Line` = 'Northwind Commercial Card' AND `Stage` = 'Closed Lost' GROUP BY ALL ORDER BY 2 DESC""")
        st.bar_chart(lost, x="Close Reason", y="lost_volume_m", y_label="Lost volume ($M)", horizontal=True)
    with right:
        st.markdown("**Inbound leads around the 9/30 launch**")
        daily = sql(f"""SELECT `Created Date`, MEASURE(`Leads`) leads FROM {mv('demand_inbound_lead_metrics')}
                        WHERE `Created Date` >= DATE'2026-09-01' GROUP BY ALL ORDER BY 1""")
        st.line_chart(daily, x="Created Date", y="leads")

    st.markdown("**What if we closed the ERP integration gap?**")
    pct = st.slider("Share of ERP-gap losses we would win back", 0, 100, 40, step=5, format="%d%%")
    by_erp = sql(f"""SELECT `ERP System`, MEASURE(`Lost Volume`) v FROM {mv('pipeline_opportunity_metrics')}
                     WHERE `Product Line` = 'Northwind Commercial Card' AND `Close Reason` = 'ERP integration gap' GROUP BY ALL ORDER BY v DESC""")
    st.metric("Recovered projected annual volume", f"${erp.v * pct / 100 / 1e6:.0f}M",
              help="Upper bound scaled by the slider; assumes recovered deals keep their original projected volume.")
    st.caption("Of which NetSuite: " + f"${by_erp.loc[by_erp['ERP System'] == 'NetSuite', 'v'].sum() * pct / 100 / 1e6:.0f}M. "
               "Native ERP sync for NetSuite and QuickBooks is the lever on this loss reason.")

    st.divider()
    recovered = float(erp.v) * pct / 100
    sc1, sc2 = st.columns([2, 3])
    with sc1:
        st.markdown("**Save this scenario**")
        with st.form("save_scenario", clear_on_submit=True):
            label = st.text_input("Name", value=f"ERP-gap recovery at {pct}%")
            note = st.text_input("Note (optional)")
            if st.form_submit_button("Save to Lakebase", type="primary"):
                try:
                    save_scenario(label, int(erp.n), float(erp.v), int(pct), recovered, note, current_user())
                    st.success("Saved.")
                except Exception as e:
                    st.warning(f"Lakebase unavailable: {e}")
    with sc2:
        st.markdown("**Saved scenarios** (Lakebase)")
        try:
            df = recent_scenarios()
            if len(df):
                df["Recovered volume"] = df["Recovered volume"].map(lambda v: f"${float(v) / 1e6:.0f}M")
                df["Recovery %"] = df["Recovery %"].map(lambda v: f"{int(v)}%")
                st.dataframe(df, hide_index=True, use_container_width=True)
            else:
                st.caption("No saved scenarios yet. Set the slider and save one.")
        except Exception as e:
            st.warning(f"Lakebase unavailable: {e}")


def tab_funnel():
    st.subheader("Where Northwind Commercial Card deals stall")
    stages = sql(f"""SELECT `Stage`, MEASURE(`Average Days In Stage`) avg_days, MEASURE(`Opportunities`) opps,
                            MEASURE(`Stalled Opportunities`) stalled, MEASURE(`Stall Rate`) stall_rate
                     FROM {mv('funnel_stage_metrics')} WHERE `Product Line` = 'Northwind Commercial Card' GROUP BY ALL""")
    stages["__o"] = stages["Stage"].map({s: i for i, s in enumerate(STAGE_ORDER)})
    stages = stages.sort_values("__o")
    slow = stages.sort_values("avg_days", ascending=False).iloc[0]["Stage"] if len(stages) else "Solution"
    stalled_pipe = sql(f"""SELECT MEASURE(`Stalled Open Pipeline`) v FROM {mv('funnel_stage_metrics')}
                           WHERE `Product Line` = 'Northwind Commercial Card'""").iloc[0].v
    c = st.columns(3)
    c[0].metric("Slowest stage", slow, help="Highest average days in stage for Northwind Commercial Card")
    c[1].metric(f"Avg days in {slow}", f"{stages.loc[stages['Stage'] == slow, 'avg_days'].iloc[0]:.0f}")
    c[2].metric("Stalled open pipeline", f"${(stalled_pipe or 0) / 1e6:.0f}M",
                help="Projected annual volume of open deals stalled in their current stage", delta_color="inverse")

    left, right = st.columns(2)
    with left:
        st.markdown("**Average days in each funnel stage**")
        st.bar_chart(stages, x="Stage", y="avg_days", y_label="Avg days in stage")
    with right:
        st.markdown(f"**What drives the {slow}-stage stall? (avg days by ERP)**")
        drv = sql(f"""SELECT `ERP System`, MEASURE(`Average Days In Stage`) avg_days FROM {mv('funnel_stage_metrics')}
                      WHERE `Product Line` = 'Northwind Commercial Card' AND `Stage` = '{slow}' GROUP BY ALL ORDER BY 2 DESC""")
        st.bar_chart(drv, x="ERP System", y="avg_days", y_label="Avg days in stage", horizontal=True)

    st.markdown("**Stalled open opportunities** (above the 75th-percentile dwell for their stage)")
    stalled = sql(f"""SELECT `Opportunity ID`, `Account Name`, `Stage`, `ERP System`, `Lead Source`,
                             MEASURE(`Max Days In Stage`) days_in_stage
                      FROM {mv('funnel_stage_metrics')}
                      WHERE `Product Line` = 'Northwind Commercial Card' AND `Is Stalled` = true AND `Is Current Stage` = true
                      GROUP BY ALL ORDER BY days_in_stage DESC""")
    st.dataframe(stalled, hide_index=True, use_container_width=True)
    if len(stalled):
        pick = st.selectbox("Drill into a stalled deal's call transcripts", stalled["Opportunity ID"].tolist())
        if pick:
            try:
                deal = deal_detail(pick)
            except Exception as e:
                deal, _ = None, st.caption(f"Deal detail (Lakebase) unavailable: {e}")
            if deal:
                st.markdown(f"**Deal {pick} · {deal['account_name']}**  (served from Lakebase)")
                dc = st.columns(5)
                vol = deal["projected_annual_volume"]
                dc[0].metric("Projected volume", f"${float(vol) / 1e6:.1f}M" if vol else "n/a")
                dc[1].metric("Stage", deal["stage"] or "n/a")
                dc[2].metric("Days in stage", f"{int(deal['days_in_stage'])}" if deal["days_in_stage"] is not None else "n/a")
                dc[3].metric("ERP system", deal["erp_system"] or "n/a")
                dc[4].metric("Lead source", deal["lead_source"] or "n/a")
                bits = [deal.get("industry"), deal.get("revenue_band")]
                if deal.get("close_reason"):
                    bits.append(f"close reason: {deal['close_reason']}")
                st.caption(" · ".join(b for b in bits if b))
            show_docs({pick}, limit=6)
            # Foundation-model feature: draft a recommended next step from the deal metrics + transcript.
            if deal and st.button(f"Draft an AI next step for {pick}", type="secondary"):
                try:
                    hits = docs_for({pick})
                    transcript = "\n".join(pdf_text(d["volume"], d["filename"]) for d in hits[:2]) if hits else ""
                    with st.spinner(f"Asking {FM_ENDPOINT}..."):
                        step = ai_next_step(deal, transcript)
                    st.markdown("**AI next step**")
                    st.markdown(step)
                    st.caption(f"Generated by {FM_ENDPOINT} (Databricks Foundation Model API)")
                except Exception as e:
                    st.warning(f"Foundation model unavailable: {e}")
            row = stalled[stalled["Opportunity ID"] == pick].iloc[0]
            st.divider()
            fc1, fc2 = st.columns([2, 3])
            with fc1:
                st.markdown("**Flag this deal for follow-up**")
                with st.form("flag_deal", clear_on_submit=True):
                    owner = st.text_input("Owner", value=current_user())
                    note = st.text_input("Note", value=f"{row['Stage']} stall, {int(row['days_in_stage'])} days")
                    if st.form_submit_button(f"Flag {pick} to Lakebase", type="primary"):
                        try:
                            flag_deal(pick, str(row["Account Name"]), str(row["Stage"]), int(row["days_in_stage"]),
                                      note, owner, current_user())
                            st.success(f"{pick} flagged for follow-up.")
                        except Exception as e:
                            st.warning(f"Lakebase unavailable: {e}")
            with fc2:
                st.markdown("**Flagged deals** (Lakebase)")
                try:
                    df = recent_followups()
                    if len(df):
                        st.dataframe(df, hide_index=True, use_container_width=True)
                    else:
                        st.caption("No deals flagged yet.")
                except Exception as e:
                    st.warning(f"Lakebase unavailable: {e}")


def tab_ask():
    st.subheader("Ask Northwind Pipeline Intelligence")
    agent = list(GENIE)[0]
    q = st.text_input("Question", value="Where do Northwind Commercial Card deals stall in the funnel, and what's driving it?")
    if st.button("Ask", type="primary") and q:
        with st.spinner("Genie is working..."):
            msg = client().genie.start_conversation_and_wait(GENIE[agent], q)
        answer, query = "", ""
        for a in msg.attachments or []:
            if a.text and a.text.content:
                answer += a.text.content + "\n"
            if a.query:
                query = a.query.query
        left, right = st.columns([3, 2])
        with left:
            st.markdown(answer or "_No answer returned._")
            if query:
                with st.expander("SQL (governed metric view)"):
                    st.code(query, language="sql")
        with right:
            st.markdown("**Related call transcripts**")
            ids = set(ID_PATTERN.findall(q + " " + answer))
            if ids:
                show_docs(ids)
            else:
                st.caption("Mention an ID (OPP-, ACCT-, CALL-) to pull its transcripts.")


def main():
    st.set_page_config(page_title="Northwind Pipeline Intelligence", page_icon="🧭", layout="wide")
    st.title("Northwind Pipeline Intelligence")
    st.caption("Northwind Commercial Card commercial pipeline: where the funnel stalls, and why. Synthetic demo data · "
               f"signed in as {current_user()}")
    tabs = st.tabs(["Leader", "Funnel", "Ask"])
    for t, fn in zip(tabs, [tab_leader, tab_funnel, tab_ask]):
        with t:
            try:
                fn()
            except Exception as e:
                st.error(f"{type(e).__name__}: {e}")


main()
