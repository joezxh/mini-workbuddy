---
source: https://docs.getsemantica.ai/cli-setup
title: CLI Setup - Semantica
---

# CLI Setup - Semantica

Installing the base package registers five executables on your `PATH`. Each serves a distinct purpose. This page explains what they are, how to verify they are available, and which one to reach for in each situation.

##  Installed Commands

```
pip install semantica
```

After installation the following commands are available:

| Command | Entry point | What it does |
| --- | --- | --- |
| `semantica` | `semantica.cli:main` | General-purpose CLI for pipeline runs, extraction, and graph operations |
| `semantica-server` | `semantica.server:main` | FastAPI/uvicorn REST API server bound to `127.0.0.1:8000` by default (set `SEMANTICA_HOST` to override) |
| `semantica-worker` | `semantica.worker:main` | Background worker process entry point for Semantica deployments |
| `semantica-explorer` | `semantica.explorer:main` | Interactive browser dashboard for knowledge graph exploration |
| `semantica-mcp` | `semantica.mcp_server:main` | MCP server (stdio) for Claude Desktop, Cursor, Windsurf, and other MCP clients |

`semantica-explorer` requires `pip install semantica[explorer]`. Running it without that extra will immediately print an error and exit. See [Explorer Setup](/explorer-setup) for the full walkthrough.

##  Verify the Installation

Confirm each command is reachable and prints its usage:

```
semantica --help
semantica-server --help
semantica-worker --help
semantica-explorer --help
semantica-mcp --help
```

Confirm the package version:

```
python -c "import semantica; print(semantica.__version__)"
```

##  When to Use Each Command

* **semantica**: general-purpose CLI. Use it for one-off pipeline runs, entity extraction, and graph operations from a shell script or CI job.
* **semantica-server**: starts the REST API server. Binds to `127.0.0.1:8000` by default; set `SEMANTICA_HOST` to expose beyond localhost. Use this when another service or application needs programmatic access to Semantica over HTTP.
* **semantica-worker**: background task processor. Run alongside `semantica-server` when you need async pipeline execution outside the request cycle. Start the server first, then start one or more workers pointing at the same backend.
* **semantica-explorer**: launches the browser dashboard. Requires `pip install semantica[explorer]`. Use this to explore a saved knowledge graph interactively. See [Explorer Setup](/explorer-setup).
* **semantica-mcp**: runs the MCP server over stdio. Configure it in your MCP client’s settings file to expose all 15 tools and 3 resources to Claude Desktop, Cursor, Windsurf, or any MCP-aware client. See [MCP Server](/reference/mcp_server).

##  Usage Examples

* REST server
* Worker
* MCP client config
* Explorer
* Python module form

```
# Starts FastAPI + uvicorn on 127.0.0.1:8000 (set SEMANTICA_HOST to change)
semantica-server
```

Once running, check it with:

```
curl http://localhost:8000/health
# {"status": "ok"}

curl http://localhost:8000/api/info
# {"name": "Semantica API", "version": "...", "status": "active"}
```

The interactive API docs are at `http://localhost:8000/docs`.

```
semantica-worker
```

The worker exits cleanly on `SIGINT` (Ctrl-C) or `SIGTERM`.

Add to your MCP client’s settings file:

```
{
  "mcpServers": {
    "semantica": {
      "command": "semantica-mcp"
    }
  }
}
```

Or use the Python module form if the command is not on `PATH`:

```
{
  "mcpServers": {
    "semantica": {
      "command": "python",
      "args": ["-m", "semantica.mcp_server"]
    }
  }
}
```

Test it directly before configuring your client:

```
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | semantica-mcp
```

You should receive a JSON-RPC response. See [MCP Server](/reference/mcp_server) for the full list of tools and resources.

```
pip install semantica[explorer]
semantica-explorer --graph my_graph.json
```

See [Explorer Setup](/explorer-setup) for the full walkthrough including how to build and save a graph file.

Every command also runs as a Python module: useful when the script directory is not on `PATH`:

```
python -m semantica.mcp_server
python -m semantica.explorer --graph my_graph.json
```

##  Environment Variables

`semantica-mcp` reads two environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `SEMANTICA_KG_PATH` | *(none)* | Path to a saved graph file to load on startup |
| `SEMANTICA_LOG_LEVEL` | `WARNING` | Log verbosity: `DEBUG`, `INFO`, `WARNING` |

`semantica-server` reads one:

| Variable | Default | Description |
| --- | --- | --- |
| `SEMANTICA_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000` | Comma-separated list of allowed CORS and WebSocket origins. The default covers the Vite dev server and the server’s own port, so a browser opened on `127.0.0.1:8000` can open the WebSocket; setting it replaces the default |

No other environment variables are read by these commands.

##  Troubleshooting

command not found

The executables land in `bin/` (Linux/Mac) or `Scripts/` (Windows) of the active Python environment. If the command is not found, that directory is likely not on `PATH`.Activate your virtual environment first:

```
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows
semantica --help
```

Find where pip placed the scripts:

```
python -m site --user-scripts   # user-level install
pip show -f semantica           # shows all installed files
```

Command found but crashes on import

```
pip install --upgrade semantica
python -c "import semantica; print(semantica.__version__)"
```

If you have multiple Python environments, install into the one the shell resolves:

```
python -m pip install semantica
```

semantica-explorer: uvicorn is required

The Explorer extras are not included in the base install:

```
pip install semantica[explorer]
```

semantica-mcp silent failure inside a MCP client

The MCP server communicates over stdio. Test it directly from the shell first:

```
echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | semantica-mcp
```

A response of `{"jsonrpc":"2.0","id":1,"result":{}}` confirms the server is working. If you see nothing, check that the command is on `PATH` and the base package is installed.

Windows: DLL errors on startup

Install the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe). This is a Windows system dependency required by PyTorch and related packages, not a Semantica bug.

##  Next Steps

* [Explorer Setup](/explorer-setup): build a graph, save it, and launch the browser dashboard.
* [MCP Server](/reference/mcp_server): all 15 tools and 3 resources exposed over the MCP protocol.
* [Installation](/installation): virtual environments, optional extras, and platform-specific notes.
* [Quickstart](/quickstart): end-to-end pipeline walkthrough with working code.
