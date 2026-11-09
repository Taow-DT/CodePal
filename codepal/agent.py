"""Agent orchestration loop.

Drives the LLM with the four built-in tools plus any MCP tools, executing tool
calls and feeding results back until the model produces a final answer. Yields
streaming events so the UI can render progress live.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterator, List, Optional

from . import tools as builtin_tools
from .mcp import MCPRegistry


SYSTEM_PROMPT = """你是一个运行在用户本地的 AI 编程助手（CodePal）。
你拥有以下四类内置工具，以及一个可扩展的 MCP 工具集：

- read_file(path): 读取工作区内文件（带行号）
- write_file(path, content): 写入/创建文件（保留 .bak 备份）
- edit_file(path, old_string, new_string): 精确替换文件中唯一匹配的文本
- run_bash(command, timeout?): 在工作区执行 shell 命令

使用规则：
1. 优先用工具去读、写、改、运行，而不是凭空编造代码或命令输出。
2. 修改文件前，先用 read_file 看清现状；edit_file 的 old_string 必须精确且唯一。
3. 运行命令注意超时；破坏性命令（rm -rf 等）要谨慎。
4. 没有工具能解决时，直接给出说明，不要假装成功。
5. 最终用中文向用户清晰汇报你做了什么、结果如何。
"""


class Agent:
    def __init__(
        self,
        llm: Any,
        workspace: str,
        mcp: Optional[MCPRegistry] = None,
        max_iterations: int = 12,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.llm = llm
        self.workspace = workspace
        self.mcp = mcp or MCPRegistry()
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt

    # -- tool dispatch ------------------------------------------------------
    def _all_schemas(self) -> List[Dict[str, Any]]:
        return builtin_tools.tool_schemas() + self.mcp.tool_schemas()

    def _execute(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name.startswith("mcp__"):
            return self.mcp.call(name, args)
        return builtin_tools.dispatch(name, self.workspace, args)

    @staticmethod
    def _format_result(name: str, res: Dict[str, Any]) -> str:
        if not res.get("ok", False):
            msg = f"[{name}] 失败: {res.get('error', '未知错误')}"
            # Surface the actual command output (e.g. stderr) so the model can
            # self-correct instead of blindly retrying and burning iterations.
            if res.get("output"):
                msg += f"\n输出:\n{res['output']}"
            if "returncode" in res:
                msg += f"\n(exit={res['returncode']})"
            return msg
        if "content" in res:
            return f"[{name}] 读取成功（{res.get('lines')} 行, {res.get('bytes')} 字节）:\n{res['content']}"
        if "output" in res:
            return f"[{name}] 输出:\n{res['output']}"
        return f"[{name}] {res.get('message', '完成')}"

    # -- main loop ----------------------------------------------------------
    def run(self, user_message: str, history: Optional[List[Dict[str, Any]]] = None
            ) -> Iterator[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        yield {"type": "run_start"}

        prev_sig = None
        repeat = 0
        for it in range(self.max_iterations):
            # Nudge the model to wrap up once we're close to the cap, so it
            # produces a final answer instead of endlessly calling tools.
            if it == self.max_iterations - 2:
                messages.append({
                    "role": "user",
                    "content": "你已接近最大迭代次数。如果任务已完成，请立即用中文给出最终总结，不要再调用工具。",
                })

            try:
                resp = self.llm.chat(messages, tools=self._all_schemas())
            except Exception as e:  # network / API errors
                yield {"type": "error", "message": str(e)}
                return

            tool_calls = resp.get("tool_calls")
            if not tool_calls:
                content = resp.get("content") or ""
                yield {"type": "assistant", "content": content}
                yield {"type": "done"}
                return

            # Detect identical tool-call patterns across iterations (a sign the
            # model is stuck retrying the same thing) and bail out early.
            sig = tuple(sorted(
                (tc.get("function", {}).get("name", ""),
                 tc.get("function", {}).get("arguments", ""))
                for tc in tool_calls
            ))
            if sig == prev_sig:
                repeat += 1
            else:
                repeat = 0
                prev_sig = sig
            if repeat >= 2:  # 3 identical iterations in a row
                yield {"type": "error",
                       "message": "检测到重复的工具调用（疑似死循环），已提前停止。请检查上一步的工具结果。"}
                return

            # Record the assistant turn. The assistant message carrying the
            # tool_calls MUST precede its tool-result messages (OpenAI rule):
            #   assistant(tool_calls) -> tool -> tool -> ...
            assistant_msg = {"role": "assistant",
                            "content": resp.get("content"),
                            "tool_calls": []}
            records = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "tool_call", "name": name, "arguments": args}
                result = self._execute(name, args)
                yield {"type": "tool_result", "name": name,
                       "ok": result.get("ok", False),
                       "output": self._format_result(name, result)}
                records.append((tc, name, args, result))

            # Append the assistant turn first, then each tool result.
            messages.append(assistant_msg)
            for (tc, name, args, result) in records:
                assistant_msg["tool_calls"].append({
                    "id": tc.get("id", name),
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", name),
                    "content": self._format_result(name, result),
                })

        yield {"type": "error", "message": "已达到最大迭代次数，仍未得出最终答案。"}
