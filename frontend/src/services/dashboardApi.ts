import type { DashboardSummary } from "../types/dashboard";
import { request } from "./request";

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return request<DashboardSummary>(`/dashboard/summary`);
}
