import type { PreviewItem } from "./types";
import { API_ACCESS_TOKEN_KEY, API_BASE_URL_KEY, apiOriginPattern, DEFAULT_API_BASE_URL, normalizeApiBaseUrl, saveApiBaseUrl } from "./apiConfig";
import "./popup.css";

declare const chrome: any;
const root = document.querySelector<HTMLDivElement>("#app")!;
let tabId: number | undefined;
let items: PreviewItem[] = [];
let site = "generic";
let applicationId = "";
let apiBaseUrl = DEFAULT_API_BASE_URL;
let connectionMessage = "尚未检查连接";
type ApplicationOption = { id: number; company: string; role: string; status: string };
let applications: ApplicationOption[] = [];

const statusLabel: Record<string, string> = { ready: "可填充", needs_review: "需检查", manual_required: "手动填写", needs_generation: "先生成答案", no_match: "未匹配", unsupported: "不支持" };
function escapeHtml(value: string) { return value.replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[character] || character)); }
async function responseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return { detail: text.slice(0, 300) }; }
}

function render() {
  root.innerHTML = `<h1>ApplyEase</h1>
    <p class="site">当前适配器：${escapeHtml(site === "greenhouse" ? "Greenhouse" : site === "lever" ? "Lever" : "通用表单")}</p>
    <label>选择申请记录<select id="application-select"><option value="">${applications.length ? "请选择公司与职位" : "登录后会显示你的申请记录"}</option>${applications.map(application => `<option value="${application.id}" ${applicationId === String(application.id) ? "selected" : ""}>${escapeHtml(application.company || "未填写公司")} · ${escapeHtml(application.role || "未填写职位")} · ${escapeHtml(application.status)}</option>`).join("")}</select></label>
    <button id="scan">扫描当前网页</button>
    <p id="status">${items.length ? `识别到 ${items.length} 个字段` : "只会扫描，不会自动填充"}</p>
    <section id="preview">${items.map((item, index) => `<label class="row"><input type="checkbox" data-index="${index}" ${item.status === "ready" ? "checked" : ""} ${item.status !== "ready" ? "disabled" : ""}/><span><strong>${escapeHtml(item.label || item.question || "未命名字段")}</strong><small>${statusLabel[item.status] || item.status}${item.warnings.length ? ` · ${escapeHtml(item.warnings[0])}` : ""}</small>${item.answer ? `<em>${escapeHtml(item.answer)}</em>` : ""}</span></label>`).join("")}</section>
    <button id="fill" ${items.some(item => item.status === "ready") ? "" : "disabled"}>填充已勾选字段</button>
    <details><summary>后端设置与账号</summary><label>API 地址<input id="api-url" type="url" value="${escapeHtml(apiBaseUrl)}" spellcheck="false"/></label><div class="actions"><button id="save-api">保存地址</button><button id="test-api">测试连接</button></div><label>邮箱<input id="auth-email" type="email" autocomplete="username"/></label><label>密码<input id="auth-password" type="password" autocomplete="current-password"/></label><div class="actions"><button id="login-api">登录账号</button><button id="logout-api">清除登录</button></div><p id="connection-status">${escapeHtml(connectionMessage)}</p></details>
    <p class="notice">ApplyEase 不会填写密码、文件、验证码或敏感字段，也不会点击提交按钮。</p>`;
  document.querySelector("#scan")?.addEventListener("click", scan);
  document.querySelector("#fill")?.addEventListener("click", fill);
  document.querySelector("#save-api")?.addEventListener("click", saveApi);
  document.querySelector("#test-api")?.addEventListener("click", testConnection);
  document.querySelector("#login-api")?.addEventListener("click", loginApi);
  document.querySelector("#logout-api")?.addEventListener("click", logoutApi);
  document.querySelector<HTMLSelectElement>("#application-select")?.addEventListener("change", event => {
    applicationId = (event.target as HTMLSelectElement).value;
    items = [];
    render();
  });
}

async function loadApplications() {
  const headers = await chrome.storage.local.get(API_ACCESS_TOKEN_KEY);
  if (typeof headers[API_ACCESS_TOKEN_KEY] !== "string" || !headers[API_ACCESS_TOKEN_KEY]) {
    applications = [];
    return;
  }
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/tracker/applications?limit=200`, { headers: { Authorization: `Bearer ${headers[API_ACCESS_TOKEN_KEY]}` } });
    const body = await responseBody(response);
    if (!response.ok || !Array.isArray(body)) throw new Error(response.status === 401 ? "登录已失效，请重新登录" : (body as { detail?: string }).detail || "无法加载申请记录");
    applications = body.filter((item: unknown): item is ApplicationOption => Boolean(item) && typeof (item as ApplicationOption).id === "number");
    if (applicationId && !applications.some(application => application.id === Number(applicationId))) applicationId = "";
  } catch (error) {
    applications = [];
    connectionMessage = error instanceof Error ? error.message : "无法加载申请记录";
  }
}

async function loginApi() {
  const email = document.querySelector<HTMLInputElement>("#auth-email")!.value.trim();
  const password = document.querySelector<HTMLInputElement>("#auth-password")!.value;
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/auth/login`, { method: "POST", headers: { "Content-Type": "application/json", "X-ApplyEase-Client": "browser-extension" }, body: JSON.stringify({ email, password }) });
    const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.detail || "登录失败");
    if (!body.access_token) throw new Error("后端没有签发扩展会话");
    await chrome.storage.local.set({ [API_ACCESS_TOKEN_KEY]: body.access_token }); await loadApplications(); connectionMessage = `已登录 ${body.user.email}`; render();
  } catch (error) { document.querySelector("#connection-status")!.textContent = error instanceof Error ? error.message : "登录失败"; }
}

async function logoutApi() {
  const stored = await chrome.storage.local.get(API_ACCESS_TOKEN_KEY); const token = stored[API_ACCESS_TOKEN_KEY];
  if (typeof token === "string" && token) {
    await fetch(`${apiBaseUrl}/api/v1/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined);
  }
  await chrome.storage.local.remove(API_ACCESS_TOKEN_KEY); applications = []; applicationId = ""; items = []; connectionMessage = "已撤销并清除登录"; render();
}

async function saveApi() {
  const input = document.querySelector<HTMLInputElement>("#api-url")!;
  try {
    const normalized = normalizeApiBaseUrl(input.value);
    const granted = await chrome.permissions.request({ origins: [apiOriginPattern(normalized)] });
    if (!granted) throw new Error("未授予访问该后端地址的权限");
    await saveApiBaseUrl(chrome.storage.local, normalized);
    apiBaseUrl = normalized; applications = []; applicationId = ""; items = []; connectionMessage = "地址已保存；为保护账号安全，请重新登录。"; render();
  } catch (error) { document.querySelector("#connection-status")!.textContent = error instanceof Error ? error.message : "保存失败"; }
}

function testConnection() {
  document.querySelector("#connection-status")!.textContent = "正在检查...";
  chrome.runtime.sendMessage({ type: "test-connection" }, (response: { ok: boolean; error?: string }) => {
    connectionMessage = response?.ok ? "连接正常" : response?.error || "连接失败"; render();
  });
}

function scan() {
  const id = Number(applicationId);
  if (!Number.isInteger(id) || id <= 0) { document.querySelector("#status")!.textContent = "请先选择一条申请记录"; return; }
  document.querySelector("#status")!.textContent = "正在扫描并匹配...";
  chrome.runtime.sendMessage({ type: "scan", applicationId: id }, (response: { ok: boolean; error?: string; tabId?: number; site?: string; items?: PreviewItem[] }) => {
    if (!response?.ok) { document.querySelector("#status")!.textContent = response?.error || "扫描失败"; return; }
    tabId = response.tabId; site = response.site || "generic"; items = response.items || []; render();
  });
}

function fill() {
  const selected = Array.from(document.querySelectorAll<HTMLInputElement>("#preview input[data-index]:checked")).map(input => items[Number(input.dataset.index)]).filter(item => item?.status === "ready");
  if (!selected.length) return;
  document.querySelector("#status")!.textContent = "正在填充...";
  chrome.runtime.sendMessage({ type: "fill", tabId, items: selected }, (response: { ok: boolean; error?: string; filled?: number }) => { document.querySelector("#status")!.textContent = response?.ok ? `已填充 ${response.filled || 0} 个字段。请检查后手动提交。` : response?.error || "填充失败"; });
}

chrome.storage.local.get(API_BASE_URL_KEY).then(async (stored: Record<string, unknown>) => { if (typeof stored[API_BASE_URL_KEY] === "string") apiBaseUrl = stored[API_BASE_URL_KEY] as string; await loadApplications(); render(); }).catch(render);
