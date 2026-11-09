# CodePal · AI 编程助手平台

一个**本地 AI 编程助手平台（CodePal）**。它把「大模型」和「四类基础工具 + 可扩展的 MCP 工具」组合成一个能读、写、改、运行代码的智能体，并通过本地 Web 界面使用；最终打包成**可双击运行的 Windows 安装包**，而不是一堆源码 zip。

> 本项目对应课程课件《Python 智能体专题》提出的四点交付要求：
> 1. **四个工具，一个都不能少** → `read` / `write` / `edit` / `bash`
> 2. **MCP 工具** → 通过 MCP 协议接入任意外部工具（文件系统、数据库、API…）
> 3. **交的不是 zip，是一个能装的包** → PyInstaller 单文件 EXE + Inno Setup 安装程序
> 4. **怎么算做好了** → 单元/冒烟测试 + MCP 集成测试 + 安装包 + README + demo

> 👉 **普通用户只想用？** 不用读源码——直接去本仓库的 **[Releases](../../releases)** 页面下载 `CodePal.exe`，双击即可运行（无需安装 Python）。详见下方「📥 下载与使用」。

---

## ✨ 功能特性

| 能力 | 说明 |
| --- | --- |
| 🧠 智能体编排 | 调用大模型 → 解析工具调用 → 执行 → 回传结果，循环直到产出最终答案 |
| 📂 四大内置工具 | `read_file` / `write_file` / `edit_file` / `run_bash`，沙箱限定在工作区内 |
| 🔌 MCP 接入 | 内置极简 MCP stdio 客户端，可连接任意 MCP Server 并自动合并其工具 |
| 💬 流式对话 | 对话过程以 NDJSON 流式返回，工具调用与结果实时渲染为卡片 |
| 🖥️ 本地 Web IDE | 资源管理器 + 对话 + 终端 + MCP 面板，深色 IDE 风格 |
| 📦 可安装包 | 单文件 `CodePal.exe`（双击即跑），并可进一步做成 `CodePal-Setup.exe` |
| 🔒 零第三方依赖 | 运行时只用 Python 标准库，打包体积小、启动快 |

---

## 📁 目录结构

```
E:/deepseek/zuoye/1103/
├── run.py                  # 程序入口（PyInstaller 打包目标）
├── pyproject.toml
├── requirements.txt
├── config.example.json     # 配置示例
├── README.md
├── codepal/                # 核心包（纯标准库）
│   ├── main.py             # 启动本地服务 + 打开浏览器
│   ├── config.py           # 配置读写
│   ├── llm.py              # OpenAI 兼容对话客户端
│   ├── tools.py            # 四大工具 + 路径沙箱
│   ├── mcp.py              # 极简 MCP stdio 客户端 + 注册表
│   ├── agent.py            # 智能体编排循环
│   ├── server.py           # 本地 HTTP 服务与 API
│   └── web/                # 前端 SPA（index.html / style.css / app.js）
├── tests/                  # 单元 / 集成 / MCP 测试
├── packaging/              # PyInstaller 构建 + Inno 安装脚本
└── demo/                   # 演示脚本（录制 demo.mp4 用）
```

---

## 📥 下载与使用（普通用户）

**最简单：去 GitHub 仓库的 Releases 页面下载 `CodePal.exe`，双击即用**，不用装 Python、不用 clone 代码。

1. 打开本仓库 → 点击 **Releases**（右侧或顶部）→ 下载 `CodePal.exe`。
2. 双击 `CodePal.exe`，浏览器自动打开 `http://127.0.0.1:8731`。
   - 若浏览器没自动打开：桌面会生成「CodePal 访问地址.url」，双击即可；或手动访问上面的地址。
3. 点击右上角 **⚙ 设置**，填入你的大模型 API Key（默认对接 DeepSeek，可改成 OpenAI 等 OpenAI 兼容接口）。
4. 在右侧对话面板下达指令，AI 会调用工具读写/运行代码，结果实时显示在左侧编辑器与终端。

> 说明：Windows 可能弹出「SmartScreen 保护」提示（因为 exe 没有代码签名证书）。这是免费的未签名程序正常现象，点「仍要运行」即可。若要彻底消除，需自行购买代码签名证书重新打包。

---

## 🚀 快速开始（开发者）

### 方式一：用安装包（推荐交付物）
1. 进入 `dist/`，双击 `CodePal.exe`。
2. 浏览器自动打开 `http://127.0.0.1:8731`。
3. 点击右上角 **⚙ 设置**，填入 API Key（默认对接 DeepSeek，可改成 OpenAI 等兼容接口）。
4. 开始对话。

### 方式二：源码运行
```bash
cd E:/deepseek/zuoye/1103
pip install -r requirements.txt        # 仅 PyInstaller 用于打包；运行本身无需安装
python -m codepal                      # 启动后浏览器自动打开
```

---

## ⚙️ 配置

配置文件位于 `%APPDATA%/CodePal/config.json`（首次保存时创建）。也可参考 `config.example.json`：

```json
{
  "llm": {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-xxxx",
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_tokens": 2048
  },
  "workspace": "C:/你的项目目录",
  "mcp_servers": []
}
```

- **base_url**：OpenAI 兼容接口地址。DeepSeek 默认 `https://api.deepseek.com/v1`；OpenAI 用 `https://api.openai.com/v1`。
- **workspace**：智能体读写的“根目录”，工具调用被限制在该目录内，防止越权访问系统文件。

---

## 🛠️ 四大工具

| 工具 | 作用 | 示例参数 |
| --- | --- | --- |
| `read_file` | 读取文件（带行号，超长自动截断） | `{"path": "src/main.py"}` |
| `write_file` | 创建/覆盖写入文件（自动保留 `.bak` 备份） | `{"path": "a.py", "content": "print(1)"}` |
| `edit_file` | 精确替换唯一匹配文本 | `{"path":"a.py","old_string":"x","new_string":"y"}` |
| `run_bash` | 在工作区执行 shell 命令 | `{"command":"pytest", "timeout": 30}` |

---

## 🔌 接入 MCP 工具

在右侧 **MCP 工具** 面板点击「＋ 连接 MCP 服务」，例如接入官方文件系统服务：

- 名称：`filesystem`
- 命令：`npx`
- 参数：`-y @modelcontextprotocol/server-filesystem C:/你的项目目录`

连接后，该 MCP Server 暴露的工具（如 `read_file` / `write_file` / `list_directory`）会自动出现在可用工具集里，大模型可像调用内置工具一样调用它们。这正是课件里「MCP 工具和普通工具有何本质区别」的答案：MCP 让工具**由外部服务按需提供、动态扩展**，而不必写死在代码里。

---

## ✅ 测试

```bash
python -m unittest tests.test_tools tests.test_agent tests.test_mcp -v
```

- `test_tools`：四大工具的单元/冒烟测试（含越权访问拦截）
- `test_agent`：智能体编排集成测试（用 FakeLLM 验证“工具调用→结果回传→最终答案”）
- `test_mcp`：MCP 集成测试（连接内置 echo MCP Server，验证 list/call）

---

## 📦 打包成安装包

```bash
python packaging/build_windows.py        # 生成 dist/CodePal.exe（单文件，双击即用）
# 若本机装了 Inno Setup：
iscc packaging/installer.iss             # 生成 release/CodePal-Setup.exe（正式安装程序）
```

或直接运行 `packaging/make_installer.bat` 一键完成上述两步。

**交付物说明**：`dist/CodePal.exe` 是“能装的包”（无需安装、双击运行、自动开浏览器）；`CodePal-Setup.exe` 是带开始菜单/桌面快捷方式的正式安装程序。两者都满足“交的不是 zip，是一个能装的包”。

---

## 🏗️ 技术架构

```
┌─────────────── 浏览器 (本地 Web UI) ───────────────┐
│  资源管理器 │ 对话(流式) │ 终端 │ MCP 面板          │
└───────────────────────┬───────────────────────────┘
                         │ HTTP / NDJSON
┌───────────────────────▼───────────────────────────┐
│  codepal/server.py  (http.server, 标准库)           │
│     │                                              │
│     ├─ /api/chat ─► Agent 编排循环                  │
│     │        ├─ LLMClient (OpenAI 兼容, urllib)     │
│     │        ├─ 四大内置工具 (tools.py)             │
│     │        └─ MCPRegistry (mcp.py) ─► MCP Server  │
│     └─ /api/tool/* , /api/files , /api/mcp/*        │
└────────────────────────────────────────────────────┘
```

**零第三方运行时依赖**：对话用 `urllib`、服务用 `http.server`、MCP 用 `subprocess` + JSON-RPC，全部标准库实现，便于打包与审计。

---

## 🔖 发布新版本（维护者）

代码已配好自动构建：给仓库打 tag 并 push，GitHub Actions 会在 Windows 上自动生成 `CodePal.exe` 并发布到 Releases。

**方式 A（推荐，自动）**
```bash
git tag v1.0.0
git push origin v1.0.0          # 触发 .github/workflows/build.yml，自动构建并上传 exe 到 Release
```

**方式 B（手动上传）**
1. 本地运行 `python packaging/build_windows.py` 生成 `dist/CodePal.exe`；
2. 在 GitHub 仓库 → Releases → New release → 把 `dist/CodePal.exe` 作为附件上传。
   （若本机装了 Inno Setup，可额外上传 `release/CodePal-Setup.exe` 正式安装包。）

---

## 📄 许可与说明

本项目采用 **MIT 许可证**（见 `LICENSE`）。运行时需自备大模型 API Key；请遵守对应服务商的使用条款。
