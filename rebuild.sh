#!/usr/bin/env bash
# =============================================================================
# Northwind Pipeline Intelligence demo: rebuild everything from scratch with one command.
#
#   ./rebuild.sh                 # full rebuild into example-workspace
#   DATABRICKS_PROFILE=x WAREHOUSE_ID=y ./rebuild.sh
#
# Idempotent: safe to rerun on a workspace where some or all pieces exist.
# Steps:
#   1. generate synthetic data, Lakeflow Connect Salesforce tables, and transcript PDFs (local, seed 42/7)
#   2. schema + volumes                                       (deploy.sql)
#   3. upload the Salesforce connector tables, Outreach export and transcripts to the volumes
#   4. Lakeflow pipeline: deploy bundle, full refresh         (pipeline/)
#   5. metric views + tags, document functions, then verify  (deploy_metric_views.sql, deploy_functions.sql, verify.sql)
#   6. Genie agent                                            (deploy_genie_agents.py -> .genie_ids.json)
#   7. Lakebase project + database                            (northwind-pi / northwind)
#   8. deal serving: gold source + Lakebase synced table      (deploy_serving.sql, deals_online)
#   9. app: deploy bundle, grant UC + Lakebase to its SP, start (app/, lakebase.sql)
#
# Requires: databricks CLI (authenticated profile), python3, psql (PostgreSQL client).
# Catalog/schema are fixed: fe_demo_catalog.northwind_pipeline (the catalog must exist).
# Independent of the northwind (commercial-loop) demo: separate schema and separate Genie space.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

export DATABRICKS_PROFILE="${DATABRICKS_PROFILE:-example-workspace}"
export WAREHOUSE_ID="${WAREHOUSE_ID:-6c8615d2e291c37f}"
P="$DATABRICKS_PROFILE"
VOL="dbfs:/Volumes/fe_demo_catalog/northwind_pipeline"
APP="northwind-pi"
LB_PROJECT="northwind-pi"
LB_BRANCH="projects/$LB_PROJECT/branches/production"
PSQL="$(command -v psql || ls /opt/homebrew/opt/postgresql@*/bin/psql 2>/dev/null | head -1 || true)"
[ -n "$PSQL" ] || { echo "psql not found (brew install postgresql@16)"; exit 1; }
jget() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
step() { echo; echo "==> $*"; }

step "1/9 Generate synthetic data, connector tables and transcripts"
rm -rf landing docs ground_truth landing_sfdc
python3 generate_northwind_data.py
python3 generate_sfdc_connector_tables.py   # mock Lakeflow Connect Salesforce output (the governed source)
python3 generate_northwind_docs.py

step "2/9 Schema and volumes"
python3 run_sql.py deploy.sql

step "3/9 Upload connector tables, Outreach export and transcripts"
for d in landing landing_sfdc call_transcripts; do
  databricks fs rm -r "$VOL/$d" -p "$P" >/dev/null 2>&1 || true   # clear stale files; the volume itself stays
done
databricks fs cp -r landing "$VOL/landing" --overwrite -p "$P" >/dev/null
databricks fs cp -r landing_sfdc "$VOL/landing_sfdc" --overwrite -p "$P" >/dev/null
databricks fs cp -r docs/call_transcripts "$VOL/call_transcripts" --overwrite -p "$P" >/dev/null
echo "  uploaded $(find landing_sfdc -type f | wc -l | tr -d ' ') connector files and $(find docs -type f | wc -l | tr -d ' ') transcripts"

step "4/9 Lakeflow pipeline (full refresh)"
(cd pipeline && databricks bundle deploy -t fevm -p "$P" && databricks bundle run northwind_pipeline_intel --full-refresh-all -t fevm -p "$P" | tail -2)

step "5/9 Metric views, functions and verification"
python3 run_sql.py deploy_metric_views.sql
python3 run_sql.py deploy_functions.sql
python3 run_sql.py verify.sql --show

step "6/9 Genie agent"
python3 deploy_genie_agents.py
GENIE_PIPELINE=$(jget 'd["Northwind Pipeline Intelligence"]' < .genie_ids.json)
echo "  Northwind Pipeline Intelligence $GENIE_PIPELINE"

step "7/9 Lakebase project and database"
ME=$(databricks current-user me -p "$P" -o json | jget 'd["userName"]')
# Self-healing: wait out any in-progress deletion, then ensure the project exists.
for i in $(seq 1 60); do
  info=$(databricks postgres get-project "projects/$LB_PROJECT" -p "$P" -o json 2>/dev/null || true)
  if [ -z "$info" ] || echo "$info" | grep -q '"delete_time"'; then
    # absent, or a deleting/tombstoned project: try to (re)create until the name frees
    databricks postgres create-project "$LB_PROJECT" --json '{"spec": {"display_name": "Northwind Pipeline Intelligence"}}' -p "$P" >/dev/null 2>&1 && { echo "  created project"; break; } || { echo "  waiting for project name to free ($i)"; sleep 10; }
  else
    echo "  project ready"; break
  fi
done
# Wait for the production endpoint to go ACTIVE before using it.
for i in $(seq 1 60); do
  st=$(databricks postgres list-endpoints "$LB_BRANCH" -p "$P" -o json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['status'].get('current_state','') if d else '')" 2>/dev/null || true)
  [ "$st" = "ACTIVE" ] && { echo "  endpoint ACTIVE"; break; } || { echo "  endpoint $st ($i)"; sleep 10; }
done
ROLE=$(databricks postgres list-roles "$LB_BRANCH" -p "$P" -o json \
  | python3 -c "import sys,json; print(next(r['name'] for r in json.load(sys.stdin) if r['status'].get('postgres_role')=='$ME'))")
if ! databricks postgres get-database "$LB_BRANCH/databases/northwind" -p "$P" >/dev/null 2>&1; then
  databricks postgres create-database "$LB_BRANCH" --database-id northwind \
    --json "{\"spec\": {\"postgres_database\": \"northwind\", \"role\": \"$ROLE\"}}" -p "$P" >/dev/null
fi
LB_HOST=$(databricks postgres list-endpoints "$LB_BRANCH" -p "$P" -o json | jget 'd[0]["status"]["hosts"]["host"]')
echo "  Lakebase host $LB_HOST"

step "8/9 Deal serving: gold source table + Lakebase synced table"
python3 run_sql.py deploy_serving.sql
ST="fe_demo_catalog.northwind_pipeline.deals_online"
databricks postgres delete-synced-table "$ST" -p "$P" >/dev/null 2>&1 || true
databricks postgres create-synced-table "$ST" --json "{\"spec\": {\"source_table_full_name\": \"fe_demo_catalog.northwind_pipeline.gold_serving_deals\", \"branch\": \"$LB_BRANCH\", \"primary_key_columns\": [\"opportunity_id\"], \"scheduling_policy\": \"SNAPSHOT\", \"postgres_database\": \"northwind\", \"create_database_objects_if_missing\": true, \"new_pipeline_spec\": {\"storage_catalog\": \"fe_demo_catalog\", \"storage_schema\": \"northwind_pipeline\"}}}" -p "$P" >/dev/null
TOKEN=$(databricks postgres generate-database-credential "$LB_BRANCH/endpoints/primary" -p "$P" -o json | jget 'd["token"]')
for i in $(seq 1 30); do
  n=$(PGPASSWORD="$TOKEN" "$PSQL" "host=$LB_HOST port=5432 dbname=northwind user=$ME sslmode=require" -tAc "SELECT count(*) FROM northwind_pipeline.deals_online" 2>/dev/null || echo 0)
  [ "${n:-0}" -gt 0 ] 2>/dev/null && { echo "  synced $n deals to Lakebase (deals_online)"; break; }
  sleep 10
done

step "9/9 App: deploy, grant UC + Lakebase, start"
(cd app && databricks bundle deploy -t fevm -p "$P" \
   --var="warehouse_id=$WAREHOUSE_ID" --var="genie_pipeline_id=$GENIE_PIPELINE")
SP=$(databricks apps get "$APP" -p "$P" -o json | jget 'd["service_principal_client_id"]')
cat > /tmp/northwind_pi_grants.sql <<SQL
GRANT USE CATALOG ON CATALOG fe_demo_catalog TO \`$SP\`;
GRANT USE SCHEMA, SELECT ON SCHEMA fe_demo_catalog.northwind_pipeline TO \`$SP\`;
SQL
python3 run_sql.py /tmp/northwind_pi_grants.sql
TOKEN=$(databricks postgres generate-database-credential "$LB_BRANCH/endpoints/primary" -p "$P" -o json | jget 'd["token"]')
PGPASSWORD="$TOKEN" "$PSQL" "host=$LB_HOST port=5432 dbname=northwind user=$ME sslmode=require" \
  -v ON_ERROR_STOP=1 -v app_sp="$SP" -q -f lakebase.sql
PGPASSWORD="$TOKEN" "$PSQL" "host=$LB_HOST port=5432 dbname=northwind user=$ME sslmode=require" -v ON_ERROR_STOP=1 \
  -c "GRANT USAGE ON SCHEMA northwind_pipeline TO \"$SP\";" \
  -c "GRANT SELECT ON northwind_pipeline.deals_online TO \"$SP\";"
echo "  Lakebase write-back tables + deal-serving grant applied for $SP"
(cd app && databricks bundle run northwind_pipeline_intel -t fevm -p "$P" | tail -1)

echo
echo "Done."
echo "  Genie: Northwind Pipeline Intelligence $GENIE_PIPELINE"
echo "  App:   $(databricks apps get "$APP" -p "$P" -o json | jget 'd["url"]')"
