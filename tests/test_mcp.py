import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codepal.mcp import MCPRegistry


class TestMCP(unittest.TestCase):
    def test_echo_server(self):
        reg = MCPRegistry()
        spec = {
            "name": "echo",
            "command": sys.executable,
            "args": [os.path.join("tests", "echo_mcp_server.py")],
        }
        info = reg.connect(spec)
        self.assertEqual(info["tool_count"], 1)

        schemas = reg.tool_schemas()
        names = [s["function"]["name"] for s in schemas]
        self.assertIn("mcp__echo__echo", names)

        res = reg.call("mcp__echo__echo", {"text": "hi"})
        self.assertTrue(res["ok"])
        self.assertIn("hi", res["output"])
        reg.disconnect_all()


if __name__ == "__main__":
    unittest.main()
