import { request } from "./request";
import type { Job } from "../types/job";
import type { TrackedApplication } from "../types/tracker";
import type {
  OpportunitySearch,
  OpportunitySearchPayload,
} from "../types/opportunity";

export function searchOpportunities(
  payload: OpportunitySearchPayload,
): Promise<OpportunitySearch> {
  return request<OpportunitySearch>("/opportunities/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function listOpportunitySearches(): Promise<OpportunitySearch[]> {
  return request<OpportunitySearch[]>("/opportunities/searches");
}

export function deleteOpportunitySearch(searchId: number): Promise<void> {
  return request<void>(
    `/opportunities/searches/${searchId}`,
    {
      method: "DELETE",
    },
    { parseJson: false },
  );
}

export function importOpportunity(
  searchId: number,
  opportunityIndex: number,
): Promise<Job> {
  return request<Job>(
    `/opportunities/searches/${searchId}/import/${opportunityIndex}`,
    { method: "POST" },
  );
}

export function importOpportunityAndTrack(
  searchId: number,
  opportunityIndex: number,
): Promise<{ job: Job; tracker: TrackedApplication }> {
  return request<{ job: Job; tracker: TrackedApplication }>(
    `/opportunities/searches/${searchId}/import-and-track/${opportunityIndex}`,
    { method: "POST" },
  );
}
