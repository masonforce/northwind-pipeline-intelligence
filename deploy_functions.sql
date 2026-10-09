-- =============================================================================
-- Northwind transcript tools: UC SQL functions over gold_documents (parsed by the pipeline).
-- Exposed to agents through the Databricks UC functions MCP server:
--   https://<workspace>/api/2.0/mcp/functions/fe_demo_catalog/northwind_pipeline
-- Fast, deterministic transcript lookup to pair with the Genie metric agent.
-- =============================================================================

CREATE OR REPLACE FUNCTION fe_demo_catalog.northwind_pipeline.northwind_documents(entity_id STRING COMMENT 'One Northwind ID, e.g. OPP-01042, ACCT-0317, CALL-0003')
RETURNS TABLE (doc_id STRING, doc_type STRING, title STRING, entity_ids ARRAY<STRING>, text STRING)
COMMENT 'Return the full text of every Outreach call transcript that mentions the given ID (OPP-, ACCT-, CALL-). Use this for what prospects actually said about a specific opportunity or account - the driver behind a stalled or lost deal. Numbers come from the Genie metric agent.'
RETURN
  SELECT doc_id, doc_type, title, entity_ids, text
  FROM fe_demo_catalog.northwind_pipeline.gold_documents
  WHERE array_contains(entity_ids, upper(trim(northwind_documents.entity_id)))
  ORDER BY doc_id
  LIMIT 25;

CREATE OR REPLACE FUNCTION fe_demo_catalog.northwind_pipeline.northwind_search_documents(
  phrase STRING COMMENT 'Word or short phrase to search for, e.g. NetSuite, controller, CSV export, month-end close')
RETURNS TABLE (doc_id STRING, doc_type STRING, title STRING, entity_ids ARRAY<STRING>, snippet STRING)
COMMENT 'Keyword search across all Outreach call transcripts when no specific ID is known, e.g. what prospects say about NetSuite or integration. Returns up to 15 matches with a snippet around the first hit; follow up with northwind_documents for full text.'
RETURN
  SELECT doc_id, doc_type, title, entity_ids,
         substr(text, greatest(1, instr(lower(text), lower(northwind_search_documents.phrase)) - 60), 360) AS snippet
  FROM fe_demo_catalog.northwind_pipeline.gold_documents
  WHERE lower(text) LIKE concat('%', lower(northwind_search_documents.phrase), '%')
  ORDER BY doc_id
  LIMIT 15;
