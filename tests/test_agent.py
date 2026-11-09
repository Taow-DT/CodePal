import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codepal.agent import Agent
from codepal.mcp import MCPRegistry


class FakeLLM:
    """Returns one tool call, then a final answer (no network)."""
    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None, tool_choice="auto", stream=False):
        self.calls += 1
        if self.calls == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "c1", "type": "function",
                    "function": {"name": "write_file",
                                 "arguments": json.dumps({"path": "out.txt",
                                                          "content": "made by agent"})},
                }],
            }
        return {"role": "assistant", "content": "已创建文件 out.txt。", "tool_calls": None}


class TestAgent(unittest.TestCase):
    def test_run_with_tool(self):
        ws = tempfile.mkdtemp()
        agent = Agent(FakeLLM(), ws, MCPRegistry())
        events = list(agent.run("请创建一个文件"))
        types = [e["type"] for e in events]
        self.assertIn("tool_call", types)
        self.assertIn("tool_result", types)
        self.assertIn("assistant", types)
        self.assertIn("done", types)
        self.assertTrue(os.path.exists(os.path.join(ws, "out.txt")))
        self.assertIn("made by agent",
                      open(os.path.join(ws, "out.txt"), encoding="utf-8").read())


class OrderCheckingLLM:
    """Like FakeLLM but asserts the OpenAI message-ordering contract."""
    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None, tool_choice="auto", stream=False):
        self.calls += 1
        # Validate: each 'tool' message must be preceded by an assistant
        # message whose tool_calls contains a matching id.
        for i, m in enumerate(messages):
            if m.get("role") == "tool":
                self.assertLess(i, len(messages) - 1)
                prev = messages[i - 1]
                self.assertEqual(prev.get("role"), "assistant")
                ids = [tc["id"] for tc in (prev.get("tool_calls") or [])]
                self.assertIn(m.get("tool_call_id"), ids)
        if self.calls == 1:
            return {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": "c1", "type": "function",
                    "function": {"name": "write_file",
                                 "arguments": json.dumps({"path": "o.txt", "content": "x"})},
                }, {
                    "id": "c2", "type": "function",
                    "function": {"name": "run_bash",
                                 "arguments": json.dumps({"command": "echo hi"})},
                }],
            }
        return {"role": "assistant", "content": "完成", "tool_calls": None}


class TestAgentOrdering(unittest.TestCase):
    def test_tool_message_ordering(self):
        ws = tempfile.mkdtemp()
        llm = OrderCheckingLLM()
        agent = Agent(llm, ws, MCPRegistry())
        list(agent.run("做两件事"))
        self.assertGreaterEqual(llm.calls, 2)


class FailingBashLLM:
    """Calls a failing bash command, then gives a final answer."""
    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None, tool_choice="auto", stream=False):
        self.calls += 1
        if self.calls == 1:
            return {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": "c1", "type": "function",
                    "function": {"name": "run_bash",
                                 "arguments": json.dumps(
                                     {"command": "python -c \"import sys; print('boom'); sys.exit(1)\""})},
                }],
            }
        return {"role": "assistant", "content": "已看到错误。", "tool_calls": None}


class TestAgentFailureOutput(unittest.TestCase):
    def test_failure_surfaces_output(self):
        ws = tempfile.mkdtemp()
        agent = Agent(FailingBashLLM(), ws, MCPRegistry())
        events = list(agent.run("运行会失败的命令"))
        results = [e for e in events if e["type"] == "tool_result"]
        self.assertTrue(results, "should have a tool_result")
        out = results[0]["output"]
        # The stderr/output and exit code must be visible so the model can self-fix.
        self.assertIn("失败", out)
        self.assertIn("输出", out)
        self.assertIn("boom", out)
        self.assertIn("exit=1", out)


class StuckLLM:
    """Never stops calling tools — must be caught by the loop guard."""
    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None, tool_choice="auto", stream=False):
        self.calls += 1
        return {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": f"c{self.calls}", "type": "function",
                "function": {"name": "run_bash",
                             "arguments": json.dumps({"command": "echo loop"})},
            }],
        }


class TestAgentLoopGuard(unittest.TestCase):
    def test_repeat_loop_is_stopped(self):
        ws = tempfile.mkdtemp()
        llm = StuckLLM()
        agent = Agent(llm, ws, MCPRegistry())
        events = list(agent.run("一直调用工具"))
        errs = [e for e in events if e["type"] == "error"]
        self.assertTrue(errs, "stuck loop should emit an error")
        self.assertIn("死循环", errs[0]["message"])
        # Must bail out far before max_iterations (12), not spin forever.
        self.assertLess(llm.calls, 6)


if __name__ == "__main__":
    unittest.main()
