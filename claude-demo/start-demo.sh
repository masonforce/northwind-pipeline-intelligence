#!/usr/bin/env bash
# Launch the contained Claude Code demo: Claude + Northwind's Databricks MCP servers
# (the Pipeline Intelligence Genie agent, the transcript functions, and Genie One).
#   ./start-demo.sh            # mint a fresh token, write .mcp.json, start Claude here
#   ./start-demo.sh --check    # same, but only list MCP server health (no session)
# The Databricks OAuth token lasts about an hour: start (or restart) the session shortly before presenting.
set -euo pipefail
cd "$(dirname "$0")"
PROFILE="${DATABRICKS_PROFILE:-example-workspace}"
HOST="$(databricks auth env --profile "$PROFILE" | python3 -c "import sys,json; print(json.load(sys.stdin)['env']['DATABRICKS_HOST'].rstrip('/'))")"
IDS=../.genie_ids.json
PIPELINE=$(python3 -c "import json; print(json.load(open('$IDS'))['Northwind Pipeline Intelligence'])" 2>/dev/null || echo "")
export NORTHWIND_DBX_TOKEN="$(databricks auth token -p "$PROFILE" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")"

# Project-scoped MCP config; the token is read from the environment, never written to disk.
cat > .mcp.json <<JSON
{
  "mcpServers": {
    "northwind-piligence": {
      "type": "http",
      "url": "$HOST/api/2.0/mcp/genie/$PIPELINE",
      "headers": {"Authorization": "Bearer \${NORTHWIND_DBX_TOKEN}"}
    },
    "northwind-documents": {
      "type": "http",
      "url": "$HOST/api/2.0/mcp/functions/fe_demo_catalog/northwind_pipeline",
      "headers": {"Authorization": "Bearer \${NORTHWIND_DBX_TOKEN}"}
    },
    "genie-one": {
      "type": "http",
      "url": "$HOST/ai-gateway/mcp-services/system.ai.genie_one_mcp",
      "headers": {"Authorization": "Bearer \${NORTHWIND_DBX_TOKEN}"}
    }
  }
}
JSON

if [ "${1:-}" = "--check" ]; then
  claude mcp list
else
  exec claude --strict-mcp-config --mcp-config .mcp.json "$@"
fi
