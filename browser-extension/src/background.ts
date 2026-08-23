import type { DetectedField, PreviewItem } from "./types";
import { getApiBaseUrl, getAuthHeaders } from "./apiConfig";

declare const chrome: any;
async function apiBase(): Promise<string> { return getApiBaseUrl(chrome.storage.local); }

async function responseBody(response: Response): Promise<any> {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return { detail: text.slice(0, 300) }; }
}

function friendlyError(error: unknown): string {
  const message = error instanceof Error ? error.message : "请求失败";
  if (/Receiving end does not exist|Could not establish connection/i.test(message)) return "无法读取当前网页。请刷新网页后重试；Chrome 内置页面不能扫描。";
  if (/Failed to fetch|NetworkError|fetch/i.test(message)) return "无法连接 ApplyEase 后端。请确认服务已启动，并检查后端地址。";
  return message;
}

chrome.runtime.onMessage.addListener((message: { type: string; applicationId?: number; tabId?: number; items?: PreviewItem[] }, _sender: unknown, sendResponse: (response: unknown) => void) => {
  if (message.type === "scan") {
    (async () => {
      try {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true }); const tab = tabs[0];
        if (!tab?.id) throw new Error("无法找到当前网页标签页");
        const detected = await chrome.tabs.sendMessage(tab.id, { type: "detect-fields" }) as { site?: string; fields: DetectedField[] };
        if (!detected.fields.length) throw new Error("当前页面没有识别到可填写字段；表单可能仍在加载，请稍后重新扫描。");
        const response = await fetch(`${await apiBase()}/api/v1/applications/${message.applicationId}/fill-preview`, { method: "POST", headers: { "Content-Type": "application/json", ...await getAuthHeaders(chrome.storage.local) }, body: JSON.stringify({ fields: detected.fields }) });
        const body = await responseBody(response); if (!response.ok) throw new Error(response.status === 401 ? "请先在扩展的后端设置中登录 ApplyEase" : response.status === 404 ? "找不到这个 Application ID" : body.detail || `后端返回错误（${response.status}）`);
        sendResponse({ ok: true, tabId: tab.id, site: detected.site || "generic", items: body.items as PreviewItem[] });
      } catch (error) { sendResponse({ ok: false, error: friendlyError(error) }); }
    })(); return true;
  }
  if (message.type === "test-connection") {
    (async () => { try { const response = await fetch(`${await apiBase()}/health/ready`, { signal: AbortSignal.timeout(5000) }); const body = await responseBody(response); if (!response.ok || body.status !== "ok") throw new Error(body.detail || `健康检查失败（${response.status}）`); sendResponse({ ok: true }); } catch (error) { sendResponse({ ok: false, error: friendlyError(error) }); } })(); return true;
  }
  if (message.type === "fill") {
    (async () => { try { if (!message.tabId) throw new Error("网页标签页已失效"); const result = await chrome.tabs.sendMessage(message.tabId, { type: "fill-fields", items: message.items || [] }); sendResponse({ ok: true, ...result }); } catch (error) { sendResponse({ ok: false, error: error instanceof Error ? error.message : "填充失败" }); } })(); return true;
  }
});
