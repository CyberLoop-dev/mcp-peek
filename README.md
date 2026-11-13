<div align="center">

<img src="assets/banner.svg" alt="mcp-peek" width="100%">

<p>
  <img alt="License" src="https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge">
  <img alt="Python" src="https://img.shields.io/badge/python-3.8%2B-fbbf24?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Dependencies" src="https://img.shields.io/badge/dependencies-zero-34d399?style=for-the-badge">
</p>

**See exactly what an MCP server offers, before you plug it into anything.**

</div>

---

## ✨ Why

[Model Context Protocol](https://modelcontextprotocol.io) servers expose tools, resources and prompts to AI apps. `mcp-peek` launches a server over stdio, performs the handshake and prints what it found: names, descriptions and parameter signatures. Handy for debugging your own server or reviewing someone else's before you trust it.

## 🚀 Usage

```bash
git clone https://github.com/CyberLoop-dev/mcp-peek.git
cd mcp-peek

# anything after -- is the server command
python mcp_peek.py -- npx -y @modelcontextprotocol/server-filesystem .
python mcp_peek.py -- python my_server.py
```

Example output:

```text
secure-filesystem-server 0.2.0 (protocol 2025-03-26)
capabilities: tools

Tools (11)
  read_file  Read the complete contents of a file
    (path: string)
  write_file  Create a new file or overwrite an existing one
    (path: string, content: string)
  ...
```

### Options

| Flag | What it does |
|---|---|
| `--json` | Print the raw result as JSON (pipe it into `jq`) |
| `--timeout N` | Seconds to wait for each reply (default 30) |

## ⚙️ How it works

1. Starts your command and speaks newline-delimited JSON-RPC 2.0 on its stdin/stdout
2. Sends `initialize`, then the `notifications/initialized` notification
3. Calls `tools/list`, `resources/list` and `prompts/list` for whatever the server advertises, following pagination cursors
4. Closes the server. It **never calls a tool**, so it is safe to point at servers you are evaluating

Only the stdio transport is supported for now. The server's stderr is hidden so the output stays clean.

## 📄 License

MIT
