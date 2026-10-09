-- Bronze: raw source-system drops, ingested incrementally.
-- The Salesforce objects come from the Lakeflow Connect destination (landing_sfdc), with their
-- Salesforce API field names - this is the governed source for the demo. Outreach calls arrive
-- as a separate export (Outreach is a separate system). _source_file keeps lineage back to the drop.

-- --------------------------------------------------------------------- Salesforce (Lakeflow Connect)
CREATE OR REFRESH STREAMING TABLE bronze_sf_account
COMMENT 'Salesforce Account, as written by the Lakeflow Connect Salesforce connector (API field names).'
AS SELECT *, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing_sfdc}/', format => 'csv', header => true, pathGlobFilter => 'account.csv');

CREATE OR REFRESH STREAMING TABLE bronze_sf_lead
COMMENT 'Salesforce Lead (Lakeflow Connect). Product interest is free text; primary campaign in Northwind_Campaign_Key__c.'
AS SELECT *, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing_sfdc}/', format => 'csv', header => true, pathGlobFilter => 'lead.csv');

CREATE OR REFRESH STREAMING TABLE bronze_sf_opportunity
COMMENT 'Salesforce Opportunity (Lakeflow Connect).'
AS SELECT *, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing_sfdc}/', format => 'csv', header => true, pathGlobFilter => 'opportunity.csv');

CREATE OR REFRESH STREAMING TABLE bronze_sf_opportunity_history
COMMENT 'Salesforce OpportunityHistory (Lakeflow Connect): one row per stage change. The funnel-stall source.'
AS SELECT *, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing_sfdc}/', format => 'csv', header => true, pathGlobFilter => 'opportunity_history.csv');

CREATE OR REFRESH STREAMING TABLE bronze_sf_campaign
COMMENT 'Salesforce Campaign (Lakeflow Connect).'
AS SELECT *, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing_sfdc}/', format => 'csv', header => true, pathGlobFilter => 'campaign.csv');

CREATE OR REFRESH STREAMING TABLE bronze_sf_campaign_member
COMMENT 'Salesforce CampaignMember (Lakeflow Connect): one row per campaign response.'
AS SELECT *, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing_sfdc}/', format => 'csv', header => true, pathGlobFilter => 'campaign_member.csv');

CREATE OR REFRESH STREAMING TABLE bronze_sf_user
COMMENT 'Salesforce User (Lakeflow Connect): opportunity owners.'
AS SELECT *, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing_sfdc}/', format => 'csv', header => true, pathGlobFilter => 'user.csv');

-- --------------------------------------------------------------------- Outreach (separate export)
CREATE OR REFRESH STREAMING TABLE bronze_outreach_calls
COMMENT 'Raw Outreach call records with transcripts (JSON lines).'
AS SELECT *, _metadata.file_path AS _source_file
FROM STREAM read_files('${landing}/outreach/', format => 'json');
