# MCP Integration

This project exposes three tools via `agents/mcp_server.py`:

| Tool | Description |
|---|---|
| `classify_announcement` | classify one announcement into a 9-event JSON output |
| `list_event_types`      | return taxonomy metadata for all event categories |
| `run_event_batch`       | run batch classification for a date range |

## 1. Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "edpt": {
      "command": "python",
      "args": ["-m", "agents.mcp_server"],
      "cwd": "/abs/path/to/a-share-pairs-agent",
      "env": {
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

After restarting Claude Desktop, you can call tools like:

> Classify this announcement: "Trading suspended pending material event disclosure."

## 2. Cursor

Use `~/.cursor/mcp.json` or workspace `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "edpt": {
      "command": "python",
      "args": ["-m", "agents.mcp_server"],
      "cwd": "/abs/path/to/a-share-pairs-agent"
    }
  }
}
```

## 3. Other MCP clients

Any client compatible with the [MCP protocol](https://modelcontextprotocol.io)
can integrate with this server. The implementation uses `FastMCP` from the
official Python SDK.

If `mcp` is not installed, importing `agents.mcp_server` exits gracefully with setup guidance.
