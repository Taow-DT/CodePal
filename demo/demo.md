# CodePal 演示脚本（用于录制 demo.mp4）

下列步骤用于向老师/评委演示「一个能装的包 + 四大工具 + MCP + 冒烟测试」：

## 0. 准备（不在镜头内）
- 已生成安装包：`dist/CodePal.exe`
- 在设置中预先填好可用的 API Key（DeepSeek / OpenAI 兼容均可）
- 准备一个演示工作区，例如 `C:/demo-workspace`，里面放一个 `main.py`（内容随意）

## 1. 双击安装包启动（对应「交的不是 zip，是一个能装的包」）
- 双击 `dist/CodePal.exe`
- 浏览器自动打开 `http://127.0.0.1:<端口>`
- 画面：顶部品牌栏 `</> CodePal`、左侧资源管理器、中间对话、右侧终端 + MCP 面板

## 2. 四大工具（对应「四个工具，一个都不能少」）
在对话中输入：
> 请在 work 区创建一个 hello.py，打印 "Hello CodePal"，然后运行它。

观察：
- 工具卡片依次出现：`write_file` → `run_bash`
- 终端面板同时可直接执行 `python hello.py` 验证输出

## 3. 读 / 改 工具
> 读取 hello.py，把打印内容改成 "Hello MCP"，再运行确认。

观察：`read_file` → `edit_file`（精确替换）→ `run_bash`

## 4. MCP 接入（对应「MCP 工具和普通工具有何本质区别」）
- 右侧 MCP 面板 → 「＋ 连接 MCP 服务」
  - 名称：`filesystem`
  - 命令：`npx`
  - 参数：`-y @modelcontextprotocol/server-filesystem C:/demo-workspace`
- 连接后，MCP 工具列表出现 `mcp__filesystem__read_file` 等
- 对话：> 用 MCP 文件系统工具列出工作区目录
- 观察：模型调用 `mcp__filesystem__list_directory` 并返回结果

## 5. 冒烟 / 集成测试（对应「怎么算做好了」）
打开终端（项目根目录）执行：
```bash
python -m unittest tests.test_tools tests.test_agent tests.test_mcp -v
```
展示 8 项测试全部 OK（含越权拦截、智能体编排、MCP echo 集成）。

## 6. 收尾
- 展示 `README.md` 与 `packaging/installer.iss`（可进一步生成 `CodePal-Setup.exe`）
- 结束录制，保存为 `demo/demo.mp4`

---

## 录屏小贴士
- 用 OBS / 系统「Xbox 游戏栏 (Win+G)」录制整个演示窗口
- 关键画面停留 2~3 秒，让工具卡片和终端输出清晰可见
- 若网络较慢，可提前在设置里把 `temperature` 调低、模型选快一点的
