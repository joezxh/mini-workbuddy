---
source: https://docs.getsemantica.ai/integrations/tableau
title: Tableau Integration - Semantica
---

# Tableau Integration - Semantica

> Pull workbook metadata, published datasource listings, and field schemas from Tableau into Semantica using Personal Access Token (PAT) or username/password authentication.

##  Installation

```
# Install with Tableau support
pip install "semantica[ingest-tableau]"

# Or install the connector separately
pip install "tableauserverclient>=0.25"
```

##  Basic Usage

```
import os
from semantica.ingest import TableauIngestor

ingestor = TableauIngestor(
    server_url=os.getenv("TABLEAU_SERVER_URL"),
    token_name=os.getenv("TABLEAU_TOKEN_NAME"),
    token_value=os.getenv("TABLEAU_TOKEN_VALUE"),
    site_name=os.getenv("TABLEAU_SITE_NAME", ""),  # empty = default site
)

# Ingest all workbooks
data = ingestor.ingest_workbooks()
print(f"Retrieved {data.row_count} workbook(s)")

# Export to Semantica document format for GraphBuilder
docs = ingestor.export_as_documents(data)
```

Use environment variables (or a `.env` file with `python-dotenv`) to keep credentials out of source code. `TableauIngestor()` with no arguments reads from `TABLEAU_*` environment variables automatically.

##  Authentication

###  Personal Access Token (PAT) — Recommended

```
ingestor = TableauIngestor(
    server_url="https://your-server.tableau.example.com",
    site_name="your-site",          # empty string = default site
    token_name="my-pat-name",
    token_value=os.getenv("TABLEAU_TOKEN_VALUE"),
)
```

###  Username / Password

```
ingestor = TableauIngestor(
    server_url="https://your-server.tableau.example.com",
    username=os.getenv("TABLEAU_USERNAME"),
    password=os.getenv("TABLEAU_PASSWORD"),
)
```

##  Environment Variables

| Variable | Description |
| --- | --- |
| `TABLEAU_SERVER_URL` | Base URL of your Tableau Server or Cloud instance |
| `TABLEAU_SITE_NAME` | Site name (empty string for the default site) |
| `TABLEAU_TOKEN_NAME` | Personal Access Token name |
| `TABLEAU_TOKEN_VALUE` | Personal Access Token value |
| `TABLEAU_USERNAME` | Tableau username (alternative to PAT) |
| `TABLEAU_PASSWORD` | Tableau password (alternative to PAT) |

##  Ingestion Methods

###  Workbooks

```
# All workbooks
data = ingestor.ingest_workbooks()

# Filter by project
data = ingestor.ingest_workbooks(project_name="Finance")
```

###  Datasources

```
data = ingestor.ingest_datasources()
# or filter:
data = ingestor.ingest_datasources(project_name="Finance")
```

###  Fields (from a specific datasource)

```
data = ingestor.ingest_fields(datasource_id="<luid>")
```

##  Export to Documents

```
docs = ingestor.export_as_documents(data)
# Each doc: {"id": str, "text": str, "metadata": {"source": "tableau", "type": ..., ...}}
```

##  Context Manager

```
with TableauIngestor(
    server_url=os.getenv("TABLEAU_SERVER_URL"),
    token_name=os.getenv("TABLEAU_TOKEN_NAME"),
    token_value=os.getenv("TABLEAU_TOKEN_VALUE"),
) as t:
    workbooks = t.ingest_workbooks()
    datasources = t.ingest_datasources()
```

##  TableauData Reference

| Field | Type | Description |
| --- | --- | --- |
| `workbooks` | `list[dict]` | Workbook metadata (id, name, project\_name, …) |
| `datasources` | `list[dict]` | Datasource metadata (id, name, type, …) |
| `fields` | `list[dict]` | Field metadata when using `ingest_fields()` |
| `server_url` | `str` | Tableau Server base URL |
| `site_name` | `str` | Site name used for ingestion |
| `row_count` | `int` | Total items in the result set |
| `ingested_at` | `datetime` | Timestamp of ingestion |
