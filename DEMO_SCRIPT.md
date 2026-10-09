# Northwind Pipeline Intelligence - demo script (~15 minutes)

One Genie agent, one app, one story: **where does the Northwind Commercial Card funnel stall, and why?** All data
is synthetic. The agent answers numbers from the governed metric views; the transcripts explain them.

Setup: run `./rebuild.sh` once. For the Claude Code scene, run `claude-demo/start-demo.sh` shortly
before presenting (the token lasts ~1 hour).

---

## Scene 1 - The stall, in the app (4 min)
Open the **Northwind Pipeline Intelligence** app, **Funnel** tab.
- "Average days in each funnel stage" - Northwind Commercial Card deals sit longest in **Solution**.
- "What drives the Solution-stage stall? (avg days by ERP)" - **NetSuite** is far above the rest.
- "Stalled open opportunities" - the live deals above the 75th-percentile dwell for their stage.
  Pick one and the panel shows its **call transcript**: the prospect's own words are the driver.

Point: the semantic layer locates the stall; the transcript explains it. Same governed definitions
everywhere, so a changed definition updates every surface at once.

## Scene 2 - Ask it in plain English (4 min)
**Ask** tab (the Genie agent):
- "Where do Northwind Commercial Card deals stall in the funnel, and what's driving it?"
- "Why did OPP-01042 close lost?" - metrics first, then the transcript panel pulls OPP-01042's calls.
- "If we closed the ERP integration gap, how much lost Northwind Commercial Card pipeline could we recover?"
  (a scenario on governed numbers; state the assumption).

## Scene 3 - The leader's read (3 min)
**Leader** tab: open pipeline, win rate, daily leads since the 9/30 launch, lost-to-ERP-gap, the
"why we lose" chart, the launch-spike line, and the what-if slider on recovering ERP-gap losses.

## Scene 4 - Same context in Claude Code (4 min)
`cd claude-demo && ./start-demo.sh`, then ask:
- "Where are Northwind Commercial Card deals stalling, and what are prospects saying about it?"
  Claude calls `northwind-piligence` (the stall numbers) and `northwind-documents` (the transcript
  quotes) in parallel and returns one brief - the same governed context, in the tool the team uses.

---

### Ground truth (from verify.sql)
- Slowest stage for Northwind Commercial Card: **Solution**; the Solution dwell is far higher for **NetSuite /
  ERP-gap** deals than for others.
- #1 close-lost reason for Northwind Commercial Card: **ERP integration gap**, concentrated in **NetSuite**.
- Win rate: **Partner** lowest, **Referral** highest.
- Inbound leads spike ~5-6x on **9/30/2026** (launch) and 10/1.
- **Launch Webinar**: most responses, lowest pipeline per response; **CFO Roundtable**: few responses,
  highest pipeline per response.
- Anchor **OPP-01042**: Northwind Commercial Card, NetSuite, Partner-sourced, $9.4M, lost to the ERP gap after a
  long Solution dwell.
