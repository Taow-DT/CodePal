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

async function openInEditor(rel) {
  const res = await api("POST", "/api/tool/read", { path: rel });
  if (!res.ok) { alert(res.error); return; }
  editorFile = rel;
  editorDirty = false;
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
  for (let i = 1; i <= lines; i++) html += `<div>${i}</div>`;
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
      // 切换侧栏面板
      document.querySelectorAll(".ab-icon").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".side-panel").forEach(p => p.classList.remove("active"));
      const target = document.querySelector(`.side-panel[data-panel="${panel}"]`);
      if (target) target.classList.add("active");
    };
  });
}
function toggleAiPanel() {
  const p = $("aipanel");
  p.classList.toggle("collapsed");
}

function initMenu() {
  const items = {
    file: [["新建文件", () => {}], ["打开文件…", () => {}], ["—", null], ["保存 (Ctrl+S)", () => saveCurrent()], ["全部保存", () => saveCurrent()]],
    edit: [["撤销", () => document.execCommand("undo")], ["重做", () => document.execCommand("redo")], ["—", null], ["查找", () => {}]],
    select: [["全选", () => { const ta=$("code-area"); ta.focus(); ta.select(); }]],
    view: [["切换资源管理器", () => toggleSidebar()], ["切换 AI 面板", () => toggleAiPanel()], ["命令面板…", () => {}]],
    goto: [["转到文件…", () => {}], ["转到行…", () => {}]],
    run: [["运行当前文件", () => {}], ["启动调试", () => {}]],
    terminal: [["新建终端", () => $("term-input").focus()], ["运行所选文本", () => {}]],
    help: [["查看帮助", () => {}], ["关于 CodePal", () => alert("CodePal · 本地 AI 编程助手平台（仿桌面 IDE 风格）")]],
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
