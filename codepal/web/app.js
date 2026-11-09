"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  return resp.json();
}

/* ============================================================
 *  文件资源管理器（左侧栏）
 * ============================================================ */
let currentPath = "";
let selectedFile = null;

async function refreshFiles(path) {
  currentPath = path || "";
  const res = await api("GET", "/api/files?path=" + encodeURIComponent(currentPath));
  if (!res.ok) { alert(res.error); return; }
  $("ws-label").textContent = (res.path && res.path !== ".") ? res.path : "CODE";
  const tree = $("file-tree");
  tree.innerHTML = "";
  if (currentPath) {
    const up = document.createElement("div");
    up.className = "file-row";
    up.innerHTML = `<span class="indent"></span>📁 ..`;
    up.onclick = () => refreshFiles(parentPath(currentPath));
    tree.appendChild(up);
  }
  for (const e of res.entries) {
    const row = document.createElement("div");
    row.className = "file-row" + (e.is_dir ? " dir" : "");
    const icon = e.is_dir ? "📁" : `<span class="ficon">📄</span>`;
    const size = e.is_dir ? "" : `${e.size}B`;
    row.innerHTML = `<span class="indent"></span>${icon} <span>${esc(e.name)}</span><span class="size">${esc(size)}</span>`;
    const rel = currentPath ? currentPath + "/" + e.name : e.name;
    if (e.is_dir) {
      row.onclick = () => refreshFiles(rel);
    } else {
      row.onclick = () => { document.querySelectorAll(".file-row.selected").forEach(r => r.classList.remove("selected")); row.classList.add("selected"); openInEditor(rel); };
    }
    tree.appendChild(row);
  }
}
function parentPath(p) { const i = p.lastIndexOf("/"); return i < 0 ? "" : p.slice(0, i); }

/* ============================================================
 *  编辑器（中间区）
 * ============================================================ */
let editorFile = "";     // 当前打开文件的相对路径
let editorDirty = false;
let breakpoints = new Set();   // 当前文件的断点行号集合

async function openInEditor(rel) {
  const res = await api("POST", "/api/tool/read", { path: rel });
  if (!res.ok) { alert(res.error); return; }
  editorFile = rel;
  editorDirty = false;
  breakpoints = new Set();
  const rf = $("run-file");
  if (rf) rf.textContent = rel;
  const ta = $("code-area");
  ta.value = res.content || "";
  ta.readOnly = false;
  updateGutter();
  updateTab(rel, false);
  updateStatusFromEditor();
}

function updateGutter() {
  const ta = $("code-area");
  const lines = ta.value.split("\n").length;
  const g = $("gutter");
  let html = "";
  for (let i = 1; i <= lines; i++) {
    const bp = breakpoints.has(i) ? " bp" : "";
    html += `<div class="gl${bp}" data-line="${i}"><span class="bpdot"></span>${i}</div>`;
  }
  g.innerHTML = html;
  g.scrollTop = ta.scrollTop;
}

function updateTab(name, dirty) {
  const tab = $("active-tab");
  tab.dataset.file = name || "";
  tab.querySelector(".tab-name").textContent = name ? name.split("/").pop() : "欢迎";
  tab.querySelector(".tab-dot").classList.toggle("hidden", !dirty);
}

function markDirty(dirty) {
  editorDirty = dirty;
  $("active-tab").querySelector(".tab-dot").classList.toggle("hidden", !dirty);
}

async function saveCurrent() {
  if (!editorFile) return;
  const res = await api("POST", "/api/tool/write", { path: editorFile, content: $("code-area").value });
  if (res.ok) { markDirty(false); }
  else alert("保存失败: " + res.error);
}

function updateStatusFromEditor() {
  const ta = $("code-area");
  const pos = ta.selectionStart;
  const before = ta.value.slice(0, pos);
  const line = before.split("\n").length;
  const col = pos - before.lastIndexOf("\n");
  $("st-pos").textContent = `行 ${line}, 列 ${col}`;
}

/* ============================================================
 *  终端（编辑器底部）
 * ============================================================ */
async function runTerminal(cmd) {
  if (!cmd.trim()) return;
  appendTerm(`PS> ${cmd}`, "cmd");
  const res = await api("POST", "/api/tool/bash", { command: cmd, timeout: 30 });
  if (res.ok) {
    const out = (res.output || "").trim();
    if (out) appendTerm(out, "ok");
  } else {
    appendTerm(res.error || "执行失败", "err");
  }
}
function appendTerm(text, cls) {
  const log = $("term-log");
  const div = document.createElement("div");
  if (cls) div.className = cls;
  div.textContent = text;
  log.appendChild(div);
  $("term-body").scrollTop = $("term-body").scrollHeight;
}

/* ============================================================
 *  AI 对话（右侧面板）
 * ============================================================ */
let currentAssistant = null;
let pendingCard = null;
let pendingTool = null;

function addUserMessage(text) {
  hideWelcome();
  const m = document.createElement("div");
  m.className = "msg user";
  m.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  $("messages").appendChild(m);
  scrollMessages();
}
function hideWelcome() { const w = $("ai-welcome"); if (w) w.style.display = "none"; }
function scrollMessages() { const el = $("messages"); el.scrollTop = el.scrollHeight; }

function welcomeHTML() {
  const examples = [
    "看看当前工作区有哪些文件",
    "用 Python 写一个快速排序",
    "读一下 README.md 并总结",
    "运行 python --version",
  ];
  const chips = examples
    .map((t) => `<button class="ex-chip" data-q="${esc(t)}">${esc(t)}</button>`)
    .join("");
  return (
    `<div class="ai-title">让想法成为现实 ✨</div>` +
    `<div class="ai-sub">一站式编程工作台，帮你读、写、改、运行代码。</div>` +
    `<div class="ai-card"><div class="ai-card-title">👋 欢迎使用 CodePal</div>` +
    `<ul><li>快速生成 / 修改代码</li><li>直接读写工作区文件</li><li>在底部终端运行命令</li></ul></div>` +
    `<div class="ai-examples"><div class="ai-ex-label">试试这些：</div>${chips}</div>`
  );
}

function initWelcomeChips() {
  document.querySelectorAll(".ex-chip").forEach((b) => {
    b.onclick = () => {
      const q = b.dataset.q || "";
      const input = $("chat-input");
      input.value = q;
      input.focus();
    };
  });
}

function handleEvent(ev) {
  if (ev.type === "run_start") {
    hideWelcome();
    currentAssistant = document.createElement("div");
    currentAssistant.className = "msg assistant";
    currentAssistant.innerHTML = `<div class="who">CodePal</div>`;
    $("messages").appendChild(currentAssistant);
    pendingCard = null;
    return;
  }
  if (ev.type === "assistant") {
    let bubble = currentAssistant.querySelector(".bubble");
    if (!bubble) {
      bubble = document.createElement("div");
      bubble.className = "bubble";
      currentAssistant.appendChild(bubble);
    }
    bubble.textContent += ev.content || "";
    scrollMessages();
    return;
  }
  if (ev.type === "tool_call") {
    pendingTool = { name: ev.name, path: ev.arguments ? ev.arguments.path : null };
    const card = document.createElement("div");
    card.className = "tool-card";
    const args = esc(JSON.stringify(ev.arguments ?? {}, null, 2));
    card.innerHTML =
      `<div class="tc-head"><span><span class="name">🔧 ${esc(ev.name)}</span></span></div>` +
      `<pre style="display:none">${args}</pre>`;
    card.querySelector(".tc-head").addEventListener("click", () => {
      const p = card.querySelector("pre");
      p.style.display = p.style.display === "none" ? "block" : "none";
    });
    currentAssistant.appendChild(card);
    pendingCard = card;
    scrollMessages();
    return;
  }
  if (ev.type === "tool_result") {
    if (pendingCard) {
      const badge = ev.ok
        ? `<span class="badge ok">成功</span>`
        : `<span class="badge fail">失败</span>`;
      pendingCard.querySelector(".tc-head").insertAdjacentHTML("beforeend", badge);
      const pre = pendingCard.querySelector("pre");
      pre.style.display = "block";
      pre.textContent = ev.output || "";
      pendingCard = null;
    }
    if (ev.ok && pendingTool && pendingTool.path &&
        (pendingTool.name === "write_file" || pendingTool.name === "edit_file")) {
      // AI 写/改文件后，自动在中间编辑器打开
      openInEditor(pendingTool.path);
    }
    pendingTool = null;
    scrollMessages();
    return;
  }
  if (ev.type === "error") {
    hideWelcome();
    const m = document.createElement("div");
    m.className = "msg assistant";
    const isKey = /api key|apikey|未配置/i.test(ev.message || "");
    const action = isKey
      ? `<div style="margin-top:8px"><button class="ai-banner-btn" onclick="openSettings()">打开设置</button></div>`
      : "";
    m.innerHTML = `<div class="who">CodePal</div><div class="bubble" style="border-color:#f48771">⚠ ${esc(ev.message)}${action}</div>`;
    $("messages").appendChild(m);
    scrollMessages();
    return;
  }
}

async function sendChat() {
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addUserMessage(message);

  const resp = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history: [] }),
  });
  if (!resp.ok) {
    handleEvent({ type: "error", message: `HTTP ${resp.status}` });
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl);
      buf = buf.slice(nl + 1);
      if (!line.trim()) continue;
      try { handleEvent(JSON.parse(line)); } catch (e) { /* ignore */ }
    }
  }
}

function newChat() {
  $("messages").innerHTML = "";
  const w = document.createElement("div");
  w.className = "ai-welcome"; w.id = "ai-welcome";
  w.innerHTML = welcomeHTML();
  $("messages").appendChild(w);
  initWelcomeChips();
}

/* 无 API Key 时的醒目标识，放在对话区顶部，避免用户以为软件坏了 */
function maybeShowKeyBanner() {
  api("GET", "/api/config").then((cfg) => {
    const hasKey = cfg.llm && cfg.llm.api_key === "********";
    const existing = document.getElementById("key-banner");
    if (hasKey) { if (existing) existing.remove(); return; }
    if (existing) return;
    const b = document.createElement("div");
    b.id = "key-banner";
    b.className = "ai-banner";
    b.innerHTML =
      `<div class="ai-banner-text">⚠ 尚未配置 API Key，AI 对话不可用。左侧文件管理、中间编辑器、底部终端均可直接使用；点击「打开设置」填写 DeepSeek / OpenAI 的 Key 后即可对话。</div>` +
      `<button class="ai-banner-btn" onclick="openSettings()">打开设置</button>`;
    const msgs = $("messages");
    msgs.insertBefore(b, msgs.firstChild);
  }).catch(() => {});
}

/* ============================================================
 *  MCP / 设置
 * ============================================================ */
async function loadMcp() {
  const res = await api("GET", "/api/mcp");
  const list = $("mcp-list");
  list.innerHTML = "";
  if (!res.servers.length) { list.innerHTML = `<div class="mcp-empty">尚未连接任何 MCP 服务。</div>`; return; }
  for (const s of res.servers) {
    const box = document.createElement("div");
    box.className = "mcp-server";
    const chips = (s.tools || []).map((t) => `<span class="tool-chip">${esc(t)}</span>`).join("");
    box.innerHTML =
      `<div class="srv-name">🔌 ${esc(s.server)} <button class="btn ghost sm" data-name="${esc(s.server)}">断开</button></div><div>${chips}</div>`;
    box.querySelector("button").onclick = () => disconnectMcp(s.server);
    list.appendChild(box);
  }
}
async function connectMcp() {
  const name = $("mcp-name").value.trim();
  const cmd = $("mcp-cmd").value.trim();
  const args = $("mcp-args").value.trim().split(/\s+/).filter(Boolean);
  if (!name || !cmd) { alert("请填写名称和命令"); return; }
  const res = await api("POST", "/api/mcp/connect", { name, command: cmd, args });
  if (res.ok) { $("mcp-name").value = ""; $("mcp-cmd").value = ""; $("mcp-args").value = ""; loadMcp(); }
  else alert("连接失败: " + res.error);
}
async function disconnectMcp(name) {
  const res = await api("POST", "/api/mcp/disconnect", { name });
  if (res.ok) loadMcp();
}
async function openSettings() {
  const cfg = await api("GET", "/api/config");
  const llm = cfg.llm || {};
  $("cfg-base-url").value = llm.base_url || "";
  $("cfg-api-key").value = llm.api_key === "********" ? "" : (llm.api_key || "");
  $("cfg-api-key").placeholder = llm.api_key === "********" ? "（已保存，留空则不修改）" : "sk-...";
  $("cfg-model").value = llm.model || "";
  $("cfg-temperature").value = llm.temperature ?? 0.3;
  $("cfg-max-tokens").value = llm.max_tokens ?? 2048;
  $("cfg-workspace").value = cfg.workspace || "";
  loadMcp();
  $("settings-modal").classList.remove("hidden");
}
async function saveSettings() {
  const cfg = {
    llm: {
      base_url: $("cfg-base-url").value.trim(),
      api_key: $("cfg-api-key").value,
      model: $("cfg-model").value.trim(),
      temperature: parseFloat($("cfg-temperature").value) || 0.3,
      max_tokens: parseInt($("cfg-max-tokens").value) || 2048,
    },
    workspace: $("cfg-workspace").value.trim(),
    mcp_servers: [],
  };
  const res = await api("POST", "/api/config", cfg);
  if (res.ok) { $("settings-modal").classList.add("hidden"); refreshFiles(""); updatePrompt(); maybeShowKeyBanner(); }
  else alert("保存失败");
}

/* ============================================================
 *  活动栏 / 侧栏切换 / 菜单 / 状态栏
 * ============================================================ */
function initActivityBar() {
  document.querySelectorAll(".ab-icon").forEach(btn => {
    btn.onclick = () => {
      const panel = btn.dataset.panel;
      if (panel === "ai") { toggleAiPanel(); return; }
      if (panel === "settings") { openSettings(); return; }
      // 点击已激活图标则收起侧栏（给出明确反馈）；切换面板时确保侧栏可见
      const already = btn.classList.contains("active");
      if (already) { toggleSidebar(); return; }
      $("sidebar").style.display = "flex";
      $("res-sidebar").style.display = "";
      document.querySelectorAll(".ab-icon").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".side-panel").forEach(p => p.classList.remove("active"));
      const target = document.querySelector(`.side-panel[data-panel="${panel}"]`);
      if (target) target.classList.add("active");
    };
  });
}
function toggleAiPanel() {
  $("aipanel").classList.toggle("collapsed");
}
function openAiPanel() {
  $("aipanel").classList.remove("collapsed");
}

function initMenu() {
  const items = {
    file: [["新建文件", () => openNewFile()], ["打开文件…", () => openFileBrowser()], ["—", null], ["保存 (Ctrl+S)", () => saveCurrent()], ["全部保存", () => saveCurrent()]],
    edit: [["撤销", () => { const ta=$("code-area"); ta.focus(); document.execCommand("undo"); }], ["重做", () => { const ta=$("code-area"); ta.focus(); document.execCommand("redo"); }], ["—", null], ["查找", () => findInEditor()]],
    select: [["全选", () => { const ta=$("code-area"); ta.focus(); ta.select(); }]],
    view: [["切换资源管理器", () => toggleSidebar()], ["切换 AI 面板", () => toggleAiPanel()], ["切换深色/浅色主题", () => toggleTheme()], ["命令面板…", () => openCommandPalette()]],
    goto: [["转到文件…", () => openFileBrowser()], ["转到行…", () => gotoLine()]],
    run: [["运行当前文件", () => runCurrentFile()], ["启动调试", () => startDebug()]],
    terminal: [["新建终端", () => $("term-input").focus()], ["运行所选文本", () => runSelectedText()]],
    help: [["查看帮助", () => showHelp()], ["关于 CodePal", () => alert("CodePal · 本地 AI 编程助手平台（仿桌面 IDE 风格）")]],
  };
  document.querySelectorAll(".mb-item").forEach(btn => {
    btn.onclick = (e) => {
      const menu = items[btn.dataset.menu];
      if (!menu) return;
      const dd = $("mb-dropdown");
      dd.innerHTML = menu.map(([label, fn]) =>
        label === "—" ? `<div class="dd-sep"></div>` : `<div class="dd-item" data-act="${esc(label)}">${esc(label)}</div>`
      ).join("");
      const rect = btn.getBoundingClientRect();
      dd.style.left = rect.left + "px";
      dd.style.top = (rect.bottom + 2) + "px";
      dd.classList.remove("hidden");
      dd.querySelectorAll(".dd-item").forEach(it => {
        it.onclick = () => {
          const entry = menu.find(([l]) => l === it.dataset.act);
          if (entry && entry[1]) entry[1]();
          dd.classList.add("hidden");
        };
      });
    };
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".mb-item") && !e.target.closest(".mb-dropdown")) $("mb-dropdown").classList.add("hidden");
  });
}
function toggleSidebar() {
  const sb = $("sidebar");
  const hidden = sb.style.display === "none";
  sb.style.display = hidden ? "flex" : "none";
  $("res-sidebar").style.display = hidden ? "" : "none";
}

function updatePrompt() {
  api("GET", "/api/config").then(cfg => {
    const ws = (cfg.workspace || "C:\\").replace(/\//g, "\\");
    $("term-prompt").textContent = `PS ${ws}>`;
  });
}

/* ============================================================
 *  可拖拽分隔条
 * ============================================================ */
function initResizers() {
  const sb = $("sidebar");
  const ai = $("aipanel");
  const resS = $("res-sidebar");
  const resA = $("res-ai");
  function start(e, side) {
    e.preventDefault();
    const startX = e.clientX;
    const sw = sb.getBoundingClientRect().width;
    const aw = ai.getBoundingClientRect().width;
    document.body.classList.add("resizing");
    function move(ev) {
      if (side === "sidebar") {
        const w = Math.min(Math.max(sw + (ev.clientX - startX), 160), 480);
        sb.style.flexBasis = w + "px"; sb.style.width = w + "px";
      } else if (side === "ai") {
        const w = Math.min(Math.max(aw - (ev.clientX - startX), 260), 640);
        ai.style.flexBasis = w + "px"; ai.style.width = w + "px";
      }
    }
    function up() { document.body.classList.remove("resizing"); window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }
  resS.addEventListener("mousedown", (e) => start(e, "sidebar"));
  resA.addEventListener("mousedown", (e) => start(e, "ai"));
}

/* ============================================================
 *  事件绑定
 * ============================================================ */
$("btn-send").onclick = sendChat;
$("chat-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});
$("btn-newchat").onclick = newChat;
$("btn-settings").onclick = openSettings;
$("btn-settings-top").onclick = openSettings;
$("btn-close-settings").onclick = () => $("settings-modal").classList.add("hidden");
$("btn-save-settings").onclick = saveSettings;
$("btn-mcp-connect").onclick = connectMcp;
$("btn-agents").onclick = () => toggleAiPanel();
$("btn-close-ai").onclick = () => $("aipanel").classList.add("collapsed");

$("code-area").addEventListener("input", () => { updateGutter(); if (!editorDirty && editorFile) markDirty(true); });
$("code-area").addEventListener("scroll", () => { $("gutter").scrollTop = $("code-area").scrollTop; });
$("code-area").addEventListener("keyup", updateStatusFromEditor);
$("code-area").addEventListener("click", updateStatusFromEditor);
$("code-area").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveCurrent(); }
});

$("term-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { const v = e.target.value; e.target.value = ""; runTerminal(v); }
});

// init
initActivityBar();
initMenu();
initResizers();
updatePrompt();
refreshFiles("");
// 初始化欢迎页（含示例指令），并按配置显示「未配置 Key」横幅
const _w = $("ai-welcome");
if (_w) { _w.innerHTML = welcomeHTML(); initWelcomeChips(); }
maybeShowKeyBanner();

/* ============================================================
 *  文件：新建 / 打开 / 命令面板 / 转到行 / 运行 / 查找 / 帮助
 * ============================================================ */
const SKIP_DIRS = new Set([".git", "__pycache__", "build", "dist", "node_modules", ".venv", "venv"]);

async function openNewFile() {
  $("nf-dir").textContent = currentPath || "(工作区根目录)";
  $("nf-name").value = "";
  $("new-file-modal").classList.remove("hidden");
  $("nf-name").focus();
}
async function doCreateFile() {
  const name = $("nf-name").value.trim();
  if (!name) { alert("请输入文件名"); return; }
  const rel = currentPath ? currentPath + "/" + name : name;
  const res = await api("POST", "/api/tool/write", { path: rel, content: "" });
  if (!res.ok) { alert("创建失败: " + res.error); return; }
  $("new-file-modal").classList.add("hidden");
  await refreshFiles(currentPath);
  openInEditor(rel);
}

async function doCreateFolder() {
  const name = $("nfd-name").value.trim();
  if (!name) { alert("请输入文件夹名称"); return; }
  const rel = currentPath ? currentPath + "/" + name : name;
  const res = await api("POST", "/api/tool/mkdir", { path: rel });
  if (!res.ok) { alert("创建失败: " + res.error); return; }
  $("new-folder-modal").classList.add("hidden");
  await refreshFiles(currentPath);
}

let ofAllFiles = [];
async function collectFiles(path) {
  const res = await api("GET", "/api/files?path=" + encodeURIComponent(path || ""));
  if (!res.ok) return [];
  let out = [];
  for (const e of res.entries) {
    if (e.is_dir && SKIP_DIRS.has(e.name)) continue;
    const rel = path ? path + "/" + e.name : e.name;
    if (e.is_dir) out = out.concat(await collectFiles(rel));
    else out.push(rel);
  }
  return out;
}
async function openFileBrowser() {
  $("of-search").value = "";
  $("open-file-modal").classList.remove("hidden");
  $("of-search").focus();
  if (!ofAllFiles.length) ofAllFiles = await collectFiles("");
  renderOpenList(ofAllFiles);
}
function renderOpenList(list) {
  const box = $("of-list");
  box.innerHTML = "";
  if (!list.length) { box.innerHTML = `<div class="of-empty">没有可打开的文件</div>`; return; }
  for (const f of list) {
    const row = document.createElement("div");
    row.className = "of-row";
    row.textContent = f;
    row.onclick = () => { $("open-file-modal").classList.add("hidden"); openInEditor(f); };
    box.appendChild(row);
  }
}

const COMMANDS = [
  { label: "新建文件", fn: () => openNewFile() },
  { label: "打开文件…", fn: () => openFileBrowser() },
  { label: "保存", fn: () => saveCurrent() },
  { label: "切换资源管理器", fn: () => toggleSidebar() },
  { label: "切换 AI 面板", fn: () => toggleAiPanel() },
  { label: "运行当前文件", fn: () => runCurrentFile() },
  { label: "启动调试", fn: () => startDebug() },
  { label: "查看帮助", fn: () => showHelp() },
];
let cmdFiles = [];
async function openCommandPalette() {
  $("cmd-input").value = "";
  $("cmd-palette-modal").classList.remove("hidden");
  $("cmd-input").focus();
  if (!cmdFiles.length) cmdFiles = await collectFiles("");
  renderCmdList("");
}
function renderCmdList(q) {
  const box = $("cmd-list");
  box.innerHTML = "";
  const ql = (q || "").toLowerCase();
  const cmds = COMMANDS.filter(c => c.label.toLowerCase().includes(ql)).map(c => ({ tag: "⚙", text: c.label, fn: c.fn }));
  const files = cmdFiles.filter(f => f.toLowerCase().includes(ql)).map(f => ({ tag: "📄", text: f, fn: () => openInEditor(f) }));
  const all = cmds.concat(files).slice(0, 300);
  if (!all.length) { box.innerHTML = `<div class="of-empty">无匹配</div>`; return; }
  for (const item of all) {
    const row = document.createElement("div");
    row.className = "of-row";
    row.textContent = item.tag + " " + item.text;
    row.onclick = () => { $("cmd-palette-modal").classList.add("hidden"); item.fn(); };
    box.appendChild(row);
  }
}

async function gotoLine() {
  const s = prompt("跳转到行号：");
  if (!s) return;
  const n = parseInt(s, 10);
  if (!n || n < 1) return;
  const ta = $("code-area");
  const lines = ta.value.split("\n");
  if (n > lines.length) { alert("行号超出范围（共 " + lines.length + " 行）"); return; }
  let pos = 0;
  for (let i = 0; i < n - 1; i++) pos += lines[i].length + 1;
  ta.focus();
  ta.setSelectionRange(pos, pos + lines[n - 1].length);
  ta.scrollTop = Math.floor((n - 1) / lines.length * ta.scrollHeight);
}

async function runCurrentFile() {
  if (!editorFile) { alert("请先在左侧或编辑器打开一个文件"); return; }
  const ext = editorFile.split(".").pop().toLowerCase();
  let cmd;
  if (ext === "py") cmd = "python \"" + editorFile + "\"";
  else if (ext === "js") cmd = "node \"" + editorFile + "\"";
  else if (ext === "bat" || ext === "cmd") cmd = "cmd /c \"" + editorFile + "\"";
  else if (ext === "sh") cmd = "bash \"" + editorFile + "\"";
  else { alert("暂不支持运行该类型文件：" + ext); return; }
  await runTerminal(cmd);
}
async function runSelectedText() {
  const ta = $("code-area");
  const sel = ta.value.slice(ta.selectionStart, ta.selectionEnd).trim();
  if (!sel) { alert("请先在编辑器中选中要作为命令运行的文本"); return; }
  await runTerminal(sel);
}

/* ============================================================
 *  调试（断点 / 变量查看 / 继续 / 单步 / 停止）
 * ============================================================ */
let debugSession = null;   // 当前调试会话 id
let debugAfter = -1;       // 已消费的调试事件游标
let debugActive = false;   // 是否停在断点处（继续/单步可用）

async function startDebug() {
  if (debugSession) stopDebug();              // 先结束上一次
  if (!editorFile) { alert("请先在左侧或编辑器打开一个 Python 文件"); return; }
  const ext = editorFile.split(".").pop().toLowerCase();
  if (ext !== "py") {
    alert("调试目前仅支持 Python 文件（.py）。已为你改用「运行当前文件」。");
    return runCurrentFile();
  }
  await saveCurrent();                        // 先保存，确保运行的是最新内容
  const bps = [...breakpoints].sort((a, b) => a - b);
  appendTerm(`▶ 启动调试: ${editorFile}` + (bps.length ? `  (断点: 行 ${bps.join(", ")})` : "  (无断点)"), "dbg");
  showDebugBar(true);
  setDebugActive(false);
  const res = await api("POST", "/api/debug/start", { path: editorFile, breakpoints: bps });
  if (!res.ok) { appendTerm("调试启动失败: " + res.error, "err"); showDebugBar(false); return; }
  debugSession = res.session;
  debugAfter = -1;
  pollDebug();
}

async function pollDebug() {
  if (!debugSession) return;
  while (debugSession) {
    const res = await api("GET", `/api/debug/events?session=${encodeURIComponent(debugSession)}&after=${debugAfter}`);
    if (!res || !res.ok) break;
    for (const ev of (res.events || [])) {
      if (typeof ev._id === "number") debugAfter = Math.max(debugAfter, ev._id);
      handleDebugEvent(ev);
    }
    if (res.ended) { endDebug(); break; }
    await new Promise(r => setTimeout(r, 400));
  }
}

function handleDebugEvent(ev) {
  if (ev.event === "output") {
    appendTerm(ev.text, "ok");
  } else if (ev.event === "break") {
    appendTerm(`⏸ 命中断点  行 ${ev.line}`, "dbg");
    const loc = ev.locals || {};
    const keys = Object.keys(loc);
    if (keys.length) {
      let s = "   变量:";
      for (const k of keys.slice(0, 40)) s += `  ${k} = ${loc[k]}`;
      appendTerm(s, "var");
    } else {
      appendTerm("   变量: (当前作用域无局部变量)", "var");
    }
    setDebugActive(true);
  } else if (ev.event === "error") {
    appendTerm("❌ 运行出错: " + ev.message, "err");
  } else if (ev.event === "done") {
    appendTerm("✔ 调试结束", "dbg");
  }
}

function debugCmd(c) {
  if (!debugSession) return;
  if (c === "c" || c === "s") setDebugActive(false);
  api("POST", "/api/debug/command", { session: debugSession, command: c });
}
function stopDebug() {
  if (!debugSession) return;
  api("POST", "/api/debug/stop", { session: debugSession });
  endDebug();
}
function endDebug() {
  debugSession = null;
  showDebugBar(false);
}
function showDebugBar(on) {
  const bar = $("debug-bar");
  if (bar) bar.classList.toggle("hidden", !on);
}
function setDebugActive(on) {
  debugActive = on;
  ["dbg-continue", "dbg-step"].forEach(id => {
    const b = $(id); if (b) b.disabled = !on;
  });
}

let findPos = 0;
async function findInEditor() {
  const q = prompt("查找：");
  if (!q) return;
  const ta = $("code-area");
  const text = ta.value;
  let idx = text.indexOf(q, findPos);
  if (idx < 0) {
    findPos = 0;
    idx = text.indexOf(q);
    if (idx < 0) { alert("未找到：" + q); return; }
    alert("已回到第一处匹配");
  }
  ta.focus();
  ta.setSelectionRange(idx, idx + q.length);
  findPos = idx + q.length;
}

async function showHelp() {
  $("help-modal").classList.remove("hidden");
}

/* ============================================================
 *  新增模态框事件绑定
 * ============================================================ */
$("btn-close-newfile").onclick = () => $("new-file-modal").classList.add("hidden");
$("btn-newfile-cancel").onclick = () => $("new-file-modal").classList.add("hidden");
$("btn-newfile-ok").onclick = doCreateFile;
$("nf-name").addEventListener("keydown", (e) => { if (e.key === "Enter") doCreateFile(); });

$("btn-close-open").onclick = () => $("open-file-modal").classList.add("hidden");
$("of-search").addEventListener("input", () => renderOpenList(ofAllFiles.filter(f => f.toLowerCase().includes($("of-search").value.toLowerCase()))));

$("btn-close-cmd").onclick = () => $("cmd-palette-modal").classList.add("hidden");
$("cmd-input").addEventListener("input", () => renderCmdList($("cmd-input").value));

$("btn-close-help").onclick = () => $("help-modal").classList.add("hidden");

["open-file-modal", "new-file-modal", "cmd-palette-modal", "help-modal", "new-folder-modal"].forEach(id => {
  $(id).addEventListener("click", (e) => { if (e.target === $(id)) $(id).classList.add("hidden"); });
});

/* 资源管理器操作按钮 + 新建文件夹 */
$("exp-newfile").onclick = () => openNewFile();
$("exp-newfolder").onclick = () => { $("nfd-dir").textContent = currentPath || "(工作区根目录)"; $("nfd-name").value = ""; $("new-folder-modal").classList.remove("hidden"); $("nfd-name").focus(); };
$("exp-refresh").onclick = () => refreshFiles(currentPath);
$("exp-collapse").onclick = () => toggleSidebar();
$("btn-newfolder-ok").onclick = doCreateFolder;
$("btn-newfolder-cancel").onclick = () => $("new-folder-modal").classList.add("hidden");
$("btn-close-newfolder").onclick = () => $("new-folder-modal").classList.add("hidden");
$("nfd-name").addEventListener("keydown", (e) => { if (e.key === "Enter") doCreateFolder(); });

/* 断点：点击行号切换 */
$("gutter").addEventListener("click", (e) => {
  const div = e.target.closest(".gl");
  if (!div) return;
  const ln = parseInt(div.dataset.line, 10);
  if (breakpoints.has(ln)) breakpoints.delete(ln); else breakpoints.add(ln);
  div.classList.toggle("bp");
});
/* 调试工具栏 */
$("dbg-continue").onclick = () => debugCmd("c");
$("dbg-step").onclick = () => debugCmd("s");
$("dbg-stop").onclick = () => stopDebug();
/* 运行和调试面板 */
const _rdb = $("run-debug-btn"); if (_rdb) _rdb.onclick = () => startDebug();
const _rrb = $("run-run-btn"); if (_rrb) _rrb.onclick = () => runCurrentFile();
/* 调试快捷键：F5 继续 / F10 单步 / Shift+F5 停止 */
document.addEventListener("keydown", (e) => {
  if (!debugSession) return;
  if (e.key === "F5") { e.preventDefault(); e.shiftKey ? stopDebug() : debugCmd("c"); }
  else if (e.key === "F10") { e.preventDefault(); debugCmd("s"); }
});

/* ============ 主题：深色 / 浅色切换 ============ */
function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light") root.classList.add("theme-light");
  else root.classList.remove("theme-light");
  try { localStorage.setItem("codepal-theme", theme); } catch (e) {}
  const btn = $("btn-theme");
  if (btn) btn.textContent = theme === "light" ? "☀" : "🌙";
  const st = $("st-theme");
  if (st) st.textContent = theme === "light" ? "浅色" : "深色";
}
function toggleTheme() {
  const cur = document.documentElement.classList.contains("theme-light") ? "light" : "dark";
  applyTheme(cur === "light" ? "dark" : "light");
}
const _themeBtn = $("btn-theme");
if (_themeBtn) _themeBtn.onclick = toggleTheme;
(function () {
  let saved = "dark";
  try { saved = localStorage.getItem("codepal-theme") || "dark"; } catch (e) {}
  applyTheme(saved);
})();

/* 状态栏主题指示项：点击切换 */
const _stTheme = $("st-theme");
if (_stTheme) _stTheme.onclick = toggleTheme;
