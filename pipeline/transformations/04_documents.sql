-- Documents: parse every Outreach transcript PDF with ai_parse_document, then index each by the
-- entity IDs it mentions. Feeds the northwind_documents / northwind_search_documents UC functions
-- (deploy_functions.sql), which give the agent a fast, deterministic transcript lookup to pair
-- with the Genie metric views (the Genie Conversation API itself does not read volumes).

CREATE OR REFRESH MATERIALIZED VIEW silver_documents_parsed
COMMENT 'Raw ai_parse_document output for every call transcript PDF.'
AS
SELECT 'call_transcripts' AS volume, path, ai_parse_document(content) AS parsed
FROM read_files('/Volumes/fe_demo_catalog/northwind_pipeline/call_transcripts/', format => 'binaryFile', pathGlobFilter => '*.pdf');

CREATE OR REFRESH MATERIALIZED VIEW gold_documents
COMMENT 'One row per Northwind transcript: full parsed text plus every entity ID it mentions (OPP-, ACCT-, CALL-).'
AS
WITH t AS (
  SELECT volume, path,
         regexp_extract(path, '([^/]+)\\.pdf$', 1) AS doc_id,
         concat_ws('\n', transform(try_cast(parsed:document:elements AS ARRAY<STRUCT<content: STRING>>), e -> e.content)) AS text
  FROM silver_documents_parsed
)
SELECT doc_id, volume, 'Call transcript' AS doc_type,
       split(text, '\n')[0] AS title,
       array_distinct(regexp_extract_all(text, '(OPP-[0-9]{5}|ACCT-[0-9]{4}|CALL-[0-9]{4})', 1)) AS entity_ids,
       text,
       path
FROM t;
