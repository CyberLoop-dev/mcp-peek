#!/usr/bin/env python3
"""mcp-peek: X-ray any MCP (Model Context Protocol) stdio server.

Usage:
    python mcp_peek.py -- npx -y @modelcontextprotocol/server-filesystem .
"""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time

PROTOCOL_VERSION = "2025-03-26"
USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def reader(stream, q):
    for line in stream:
        q.put(line)
    q.put(None)


class Client:
    def __init__(self, cmd, timeout):
        self.timeout = timeout
        self.next_id = 1
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
        )
        self.q = queue.Queue()
        threading.Thread(target=reader, args=(self.proc.stdout, self.q), daemon=True).start()

    def send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self.send(msg)

    def request(self, method, params=None):
        mid = self.next_id
        self.next_id += 1
        msg = {"jsonrpc": "2.0", "id": mid, "method": method}
        if params is not None:
            msg["params"] = params
        self.send(msg)
        end = time.time() + self.timeout
        while True:
            left = end - time.time()
            if left <= 0:
                raise TimeoutError(f"no response to {method} within {self.timeout:g}s")
            try:
                line = self.q.get(timeout=left)
            except queue.Empty:
                continue
            if line is None:
                raise RuntimeError("server closed its output before answering")
            try:
                data = json.loads(line)
            except ValueError:
                continue  # not JSON-RPC (stray log line), ignore
            if data.get("id") == mid and "method" not in data:
                if "error" in data:
                    raise RuntimeError(f"{method} failed: {data['error'].get('message', data['error'])}")
                return data.get("result", {})

    def list_all(self, method, key):
        items, cursor = [], None
        while True:
            res = self.request(method, {"cursor": cursor} if cursor else {})
            items += res.get(key, [])
            cursor = res.get("nextCursor")
            if not cursor:
                return items

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


def first_line(text):
    return (text or "").strip().splitlines()[0] if (text or "").strip() else ""


def describe_params(schema):
    props = (schema or {}).get("properties", {}) or {}
    required = set((schema or {}).get("required", []) or [])
    parts = []
    for name, spec in props.items():
        typ = spec.get("type", "any") if isinstance(spec, dict) else "any"
        if isinstance(typ, list):
            typ = "|".join(typ)
        parts.append(f"{name}{'' if name in required else '?'}: {typ}")
    return parts


def main():
    ap = argparse.ArgumentParser(description="List the tools, resources and prompts of an MCP stdio server.")
    ap.add_argument("command", nargs=argparse.REMAINDER, help="server command, after --")
    ap.add_argument("--timeout", type=float, default=30, help="seconds to wait for each reply (default 30)")
    ap.add_argument("--json", action="store_true", help="print raw JSON instead of a pretty summary")
    args = ap.parse_args()

    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not cmd:
        ap.error("give the server command after --, e.g. -- npx -y @modelcontextprotocol/server-filesystem .")

    try:
        cl = Client(cmd, args.timeout)
    except FileNotFoundError:
        sys.exit(f"mcp-peek: command not found: {cmd[0]}")

    try:
        init = cl.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcp-peek", "version": "0.1.0"},
        })
        cl.notify("notifications/initialized")
        caps = init.get("capabilities", {}) or {}
        result = {"server": init.get("serverInfo", {}), "protocolVersion": init.get("protocolVersion"),
                  "capabilities": sorted(caps.keys())}
        if "tools" in caps:
            result["tools"] = cl.list_all("tools/list", "tools")
        if "resources" in caps:
            result["resources"] = cl.list_all("resources/list", "resources")
        if "prompts" in caps:
            result["prompts"] = cl.list_all("prompts/list", "prompts")
    except (TimeoutError, RuntimeError) as e:
        sys.exit(f"mcp-peek: {e}")
    finally:
        cl.close()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    srv = result["server"]
    print(c("1;36", f"{srv.get('name', '?')} {srv.get('version', '')}".strip()),
          c("2", f"(protocol {result['protocolVersion']})"))
    print(c("2", "capabilities: " + (", ".join(result["capabilities"]) or "none")))

    tools = result.get("tools", [])
    if "tools" in result:
        print("\n" + c("1;32", f"Tools ({len(tools)})"))
        for t in tools:
            print(f"  {c('1', t['name'])}  {c('2', first_line(t.get('description')))}")
            params = describe_params(t.get("inputSchema"))
            if params:
                print("    " + c("2", "(" + ", ".join(params) + ")"))
    for key, label in (("resources", "Resources"), ("prompts", "Prompts")):
        if key in result:
            print("\n" + c("1;33", f"{label} ({len(result[key])})"))
            for r in result[key]:
                name = r.get("name") or r.get("uri")
                print(f"  {c('1', name)}  {c('2', first_line(r.get('description')))}")


if __name__ == "__main__":
    main()
