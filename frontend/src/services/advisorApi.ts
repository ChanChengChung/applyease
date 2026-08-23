import { request } from "./request";
import type {
  AdvisorMessage,
  AdvisorReply,
  AdvisorContext,
  SavedAdvisorMessage,
} from "../types/advisor";

export function getAdvisorHistory(): Promise<SavedAdvisorMessage[]> {
  return request<SavedAdvisorMessage[]>("/advisor/history");
}

export function clearAdvisorHistory(): Promise<void> {
  return request<void>("/advisor/history", { method: "DELETE" });
}

export function askAdvisor(
  message: string,
  history: AdvisorMessage[],
  language: string,
  context: AdvisorContext,
): Promise<AdvisorReply> {
  return request<AdvisorReply>("/advisor/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      language,
      active_page: context.activePage,
      active_job_id: context.activeJobId,
      history: history
        .slice(-8)
        .map(({ role, content }) => ({ role, content })),
    }),
  });
}
