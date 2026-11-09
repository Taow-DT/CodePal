"""A tiny MCP stdio server used by the test-suite (echo tool).

It speaks just enough JSON-RPC to satisfy CodePal's minimal MCP client.
Run as:  python tests/echo_mcp_server.py
"""
import json
import sys


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "echo", "version": "1.0"},
            }})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [{
                "name": "echo",
                "description": "回显输入文本",
                "inputSchema": {"type": "object",
                                "properties": {"text": {"type": "string"}},
                                "required": ["text"]},
            }]}})
        elif method == "tools/call":
            args = msg.get("params", {}).get("arguments", {})
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": "echo:" + str(args.get("text", ""))}],
                "isError": False,
            }})
        else:
            send({"jsonrpc": "2.0", "id": rid, "result": {}})


if __name__ == "__main__":
    main()
