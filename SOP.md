# CodePal 运行完成 SOP（标准操作流程）

> 目标：照着这份 SOP，从零把 **CodePal（本地 AI 编程助手）** 跑起来，并成功让它「读 / 写 / 改 / 运行」代码、接上 MCP 工具、完成一次真实任务。
>
> 适用版本：本仓库 `E:/deepseek/zuoye/1103`，安装包 `dist/CodePal.exe`（单文件，双击即用）。

---

## 0. 前置条件（一次性检查）

| 项目 | 要求 | 检查方式 |
|---|---|---|
| 操作系统 | Windows 10/11 | — |
| Python | 3.10+（仅「源码运行」时需要） | `python --version` |
| Node.js / npx | 仅「连接官方 MCP Server」时需要 | `node -v`、`npx -v` |
| 大模型 API Key | DeepSeek / OpenAI 等 OpenAI 兼容接口 | 自备 `sk-...` |

> 用安装包（EXE）运行**不需要** Python/Node；只有源码模式和接官方 MCP 才需要。

---

## 1. 启动平台（两种方式任选）

### 方式 A：双击安装包（推荐，最简单）
1. 打开 `E:/deepseek/zuoye/1103/dist/CodePal.exe`。
2. 程序会自动打开浏览器，地址形如 `http://127.0.0.1:xxxxx`。
3. 若浏览器没弹出来：打开 `%TEMP%/CodePal/codepal.log`，找到 `started on http://127.0.0.1:xxxxx` 那行，手动访问该地址。

### 方式 B：源码运行
```bash
cd E:/deepseek/zuoye/1103
python -m codepal
```
同样会自动开浏览器。

界面三栏（**可拖拽中间分隔条调节大小**）：
- **左**：资源管理器 + 代码预览（AI 生成的代码会实时显示在这里）
- **中下**：终端（直接执行 shell 命令）
- **右**：AI 模块（在这里输入你的要求）

---

## 2. 配置大模型（必须，否则只能报错）

1. 点右上角 **⚙ 设置**。
2. 按服务商填写：
   - **DeepSeek**：`API Base URL = https://api.deepseek.com/v1`，`模型 = deepseek-chat`
   - **OpenAI**：`API Base URL = https://api.openai.com/v1`，`模型 = gpt-4o-mini`
3. `API Key` 填你自己的 `sk-...`。
4. 点 **保存**。右上角会从「未配置模型」变成「模型名 @ 域名」。
5. 配置保存在 `%APPDATA%/CodePal/config.json`，下次启动自动生效。

---

## 3. 跑通「四大工具」（验收第一步）

在**右侧 AI 输入框**发这一句（Enter 发送，Shift+Enter 换行）：

> 在工作区新建 hello.py，内容是 `print("Hello CodePal")`，然后运行它

预期在右侧依次看到工具卡片：
- `write_file` ✅ 已写入 N 字节
- `run_bash` ✅ 输出 `Hello CodePal`
- 左侧「代码预览」**自动打开** `hello.py` 并显示内容
- 底部出现中文总结

再试修改（验证 `read_file` / `edit_file`）：
> 读取 hello.py，把 Hello CodePal 改成 Hello MCP，再运行确认

预期：`read_file` → `edit_file` → `run_bash`，输出变为 `Hello MCP`。

✅ 四大工具（read / write / edit / bash）全部跑通即过关。

---

## 4. 接 MCP 工具（验收第二步，课件重点）

1. 右侧 AI 面板最底部，点开 **🔌 MCP 工具服务**。
2. 填三项后点 **连接**：
   - 名称：`filesystem`
   - 命令：`npx`
   - 参数：`-y @modelcontextprotocol/server-filesystem C:/你的项目目录`
3. 连接成功后，列表出现 `mcp__filesystem__read_file` 等工具芯片。
4. 在对话里说：
   > 用 filesystem 工具列出 C:/你的项目目录 下的文件
   模型会自动调用对应的 MCP 工具。

带环境变量的服务（如 GitHub）用接口接入：
```bash
curl -X POST http://127.0.0.1:<端口>/api/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{"name":"github","command":"npx",
       "args":["-y","@modelcontextprotocol/server-github"],
       "env":{"GITHUB_TOKEN":"ghp_xxx"}}'
```
断开：`POST /api/mcp/disconnect` 传 `{"name":"github"}`；查看：`GET /api/mcp`。

---

## 5. 完成一次「真实任务」（综合演练）

在右侧输入一个完整需求，例如：
> 用 Python 写一个 9×9 乘法表脚本 multiplication_table.py，并运行验证输出正确。

完成后应满足：
- 左侧代码预览显示 `multiplication_table.py` 内容；
- 右侧有 `write_file` + `run_bash` 成功记录，终端/工具结果里能看到乘法表；
- 最后有一条**中文总结**（不会卡在「已达到最大迭代次数」）。

> ⚠️ 若右侧出现红字「检测到重复的工具调用（疑似死循环）」或「已达到最大迭代次数」，说明模型在无效重试。本版本已做两处防护：① 失败会把命令报错（stderr/exit 码）回传给模型；② 临近上限会提醒模型收尾。仍卡住时，把需求写得更明确、或重启程序即可。

---

## 6. 验收 / 交付（对应课件「怎么算做好了」）

```bash
cd E:/deepseek/zuoye/1103
# 跑测试（应全部 OK）
python -m unittest tests.test_tools tests.test_agent tests.test_mcp -v

# 重新打包成安装包
python packaging/build_windows.py
# 产物：dist/CodePal.exe
```

交付物清单：
- `dist/CodePal.exe` —— 可双击运行的安装包
- `README.md` —— 项目说明
- `SOP.md` —— 本操作手册
- `demo/demo.md` —— demo 录制脚本（用 Win+G 录成 `demo/demo.mp4`）
- 测试截图 / 运行截图

---

## 7. 常见问题速查

| 现象 | 原因 | 处理 |
|---|---|---|
| 浏览器没自动打开 | 某些环境不弹窗 | 看 `%TEMP%/CodePal/codepal.log` 里的地址手动访问 |
| 所有对话都报错 4xx/5xx | 没填或填错 API Key | 右上角 ⚙ 重新填 Key 和 Base URL |
| `run_bash ❌ 未知的错误` | 命令本身报错，旧版丢 stderr | 已修复；现在会显示具体报错与 exit 码，照着改命令 |
| 报「已达到最大迭代次数」 | 模型反复重试无效动作 | 需求写明确些；或在 `agent.py` 调大 `max_iterations` |
| MCP 连不上 | `npx` 不在 PATH / 下载超时 | 用 `npx` 绝对路径，或先手动 `npx -y @modelcontextprotocol/server-filesystem .` 验证 |
| 改了源码要生效 | 浏览器缓存 | 刷新页面；若改了 Python，重启 EXE 或重跑 `python -m codepal` |

---

## 8. 一句话总结流程

**双击 CodePal.exe → ⚙ 填 API Key 保存 → 右侧输入需求（如"写乘法表并运行"）→ 看左侧代码自动生成、右侧工具执行 → 得到中文总结 = 成功完成。**

需要接外部能力时，右侧底部连一个 MCP Server 即可。验收用 `python -m unittest` 跑测试 + `python packaging/build_windows.py` 重打包。
