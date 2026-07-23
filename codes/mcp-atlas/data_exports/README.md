# Data Exports for MCP Server Testing

This directory contains sample data that can be uploaded to various online services to create test environments that match the state used in existing test prompts and evaluations.

## Purpose

Many MCP servers connect to external services, but most are relatively stateless.
However, there are 5 MCP servers (Airtable, Google Calendar, Notion, MongoDB, Slack) that require:
1. An account with the service
2. Data uploaded to that account
3. API keys or connection strings to access that data

To reproduce test results or run evaluations against known data states, you'll need to set up these services with the provided sample data.

## Available Data Exports

| Service | File | Description |
|---------|------|-------------|
| Airtable | https://airtable.com/appIF9byLfQwdHqE2/shr1KTZOgPl0qQmA8 | At that URL, click "Copy base" button to clone the DB |
| Google Calendar | `calendar_mcp_eval_export.zip` | Sample calendar events (unzip as .ics) (8KB) |
| Notion | `notion_mcp_eval_export.zip` | Sample pages and databases (13MB) |
| MongoDB | `mongo_dump_video_game_store.zip` | Sample video game store database (unzip as folder) (486KB) |
| Slack | `slack_mcp_eval_export.zip` | Sample workspace data (27KB) events timestamped for early Dec 2025 (slack free accounts hide messages older than 90 days) |

## Setup

The setup instructions for these will generate API keys that should be used in your `.env` file.

### Airtable
Create an Airtable account, and visit [https://airtable.com/appIF9byLfQwdHqE2/shr1KTZOgPl0qQmA8](https://airtable.com/appIF9byLfQwdHqE2/shr1KTZOgPl0qQmA8) and click "Copy base" to create a clone of the database. Then get an API key and set in your `.env` file as `AIRTABLE_API_KEY`.

### Google Calendar (google-workspace)
Unzip `calendar_mcp_eval_export.zip` which contains a `.ics` file, login to your google account (preferably a new account since it will import calendar events), import the data by going to [https://calendar.google.com/calendar/u/0/r/settings/export](https://calendar.google.com/calendar/u/0/r/settings/export) (make sure it's using the correct google account) and importing the `.ics` file. To get the necessary `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` for the `google-workspace` MCP server, see "Prerequesites" and "Setup Instructions" at [https://github.com/epaproditus/google-workspace-mcp-server](https://github.com/epaproditus/google-workspace-mcp-server?tab=readme-ov-file#prerequisites)

### Notion
Create a Notion account, then go into Settings > Import, and import `mcp-atlas-notion-data.zip`. This should take maximum a few minutes, and upload 6 tables and 1 page. Confirm that all 6 tables have data after a few minutes (Notion will load the data async). If any table is empty, delete the page, and re-upload the individual CSV. Next, go to [https://www.notion.so/profile/integrations](https://www.notion.so/profile/integrations) and add a new integration (type is Internal) and get the `Internal Integration Secret` and save it as `NOTION_TOKEN` in `.env`

### MongoDB
Create a MongoDB account, get your MongoDB connection URI, unzip `mongo_dump_video_game_store.zip`. Then upload the folder by doing like `mongorestore --uri="mongodb+srv://<username>:<password>@<cluster-url>" mongo_dump_video_game_store` . You may need to [install the mongodb CLI](https://www.mongodb.com/docs/mongocli/current/install/) if you don't have it yet. Save the connection URI as `MONGODB_CONNECTION_STRING` in `.env`

### Slack
Create a new slack workspace, then go to https://<your-slack-workspace-name>.slack.com/services/import and import `slack_mcp_eval_export.zip` . Note that free slack accounts have a 90-day limit, and messages sent older than that unfortunately won't be visible. You can modify the contents to have timestamps that are newer, or have a paid Slack account for $9 USD/month. You'll need to get `SLACK_MCP_XOXC_TOKEN` and `SLACK_MCP_XOXD_TOKEN` by following these instructions [https://github.com/korotovsky/slack-mcp-server/blob/HEAD/docs/01-authentication-setup.md](https://github.com/korotovsky/slack-mcp-server/blob/HEAD/docs/01-authentication-setup.md)

## Note

Without this sample data, MCP servers will still function but may return empty results or errors when test prompts reference specific data that doesn't exist in your accounts.
