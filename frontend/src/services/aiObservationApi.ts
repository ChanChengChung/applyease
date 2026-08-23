import type { AIMetrics } from "../types/aiObservation";
import { request } from "./request";

export async function getAIMetrics(days = 30): Promise<AIMetrics> {
  return request<AIMetrics>(`/ai/metrics?days=${days}`);
}
