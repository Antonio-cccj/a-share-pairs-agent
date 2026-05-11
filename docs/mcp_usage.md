# MCP 集成 / MCP integration

本项目通过 `agents/mcp_server.py` 暴露 3 个工具：

| 工具名 | 描述 |
|---|---|
| `classify_announcement` | 单条公告 → 9 类事件 JSON |
| `list_event_types`      | 列出 9 类事件分类元数据 |
| `run_event_batch`       | 对数据库内某个日期范围批量分类 |

## 一、Claude Desktop

在 `~/Library/Application Support/Claude/claude_desktop_config.json`
（macOS）或 `%APPDATA%\Claude\claude_desktop_config.json`（Windows）
中添加：

```json
{
  "mcpServers": {
    "edpt": {
      "command": "python",
      "args": ["-m", "agents.mcp_server"],
      "cwd": "/abs/path/to/event-driven-pairs-trading-cn",
      "env": {
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

重启 Claude Desktop 之后，对话中即可调用：

> 帮我分析一下 “公司股票自2023年起停牌，等待重大事项披露。” 这条公告。

## 二、Cursor

`~/.cursor/mcp.json` 或项目根目录 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "edpt": {
      "command": "python",
      "args": ["-m", "agents.mcp_server"],
      "cwd": "/abs/path/to/event-driven-pairs-trading-cn"
    }
  }
}
```

## 三、Cline / 其他 MCP 客户端

任何遵守 [MCP 协议](https://modelcontextprotocol.io) 的客户端均可接入，
本项目使用官方 `mcp` Python SDK 的 `FastMCP` 封装。

> 没装 `mcp` 时直接 `import agents.mcp_server` 会优雅地打印安装指引而非崩溃。
