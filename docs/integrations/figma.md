# Figma MCP (disabled)

Official Figma MCP server. Token from Figma account settings.

```json
{
  "mcpServers": {
    "figma": {
      "url": "https://mcp.figma.com/mcp",
      "headers": {
        "Authorization": "Bearer ${FIGMA_ACCESS_TOKEN}"
      }
    }
  }
}
```

Copy to `~/.cursor/mcp.json` or `.cursor/mcp.json` when enabled. Never commit tokens.
