import type {
  LearningResource,
  StarterPlan,
  ResearchPlan,
} from "../types/resource";
import type { Experience } from "../types/experience";
import { request } from "./request";

export type ResourceOptions = {
  level?: "beginner" | "intermediate" | "advanced";
  max_total_hours?: number;
  free_only?: boolean;
  limit?: number;
  goal?: "skills" | "project" | "interview";
  language?: "en" | "zh-CN" | "zh-TW";
};
export async function getRecommendations(
  jobId: number,
  options: ResourceOptions = {},
): Promise<LearningResource[]> {
  const params = new URLSearchParams({ job_id: String(jobId) });

  if (options.level) params.set("level", options.level);

  if (options.max_total_hours)
    params.set("max_total_hours", String(options.max_total_hours));

  if (options.free_only) params.set("free_only", "true");

  if (options.limit) params.set("limit", String(options.limit));

  if (options.goal) params.set("goal", options.goal);

  if (options.language) params.set("language", options.language);

  return request<LearningResource[]>(
    `/resources/recommendations?${params.toString()}`,
  );
}

export async function getStarterPlan(payload: {
  interest: string;
  weekly_hours: number;
  weeks: number;
  experience_level: "none" | "basic" | "some";
  goal: "explore" | "portfolio" | "competition";
  preferred_formats: Array<"project" | "competition" | "feedback" | "course">;
  experience_level_other?: string;
  goal_other?: string;
  preferred_format_other?: string;
  language: "en" | "zh-CN" | "zh-TW";
}): Promise<StarterPlan> {
  return request<StarterPlan>("/resources/starter-plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export function getSavedStarterPlan(): Promise<StarterPlan> {
  return request<StarterPlan>("/resources/starter-plans");
}
export function updateStarterPlan(
  id: number,
  payload: Pick<StarterPlan, "focus" | "headline" | "first_action" | "milestones">,
): Promise<StarterPlan> {
  return request<StarterPlan>(`/resources/starter-plans/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export function refineStarterPlan(
  id: number,
  payload: {
    weekly_hours: number;
    weeks: number;
    goal: "skills" | "project" | "interview";
    learning_style: "hands_on" | "guided" | "intensive";
    language: "en" | "zh-CN" | "zh-TW";
  },
): Promise<StarterPlan> {
  return request<StarterPlan>(`/resources/starter-plans/${id}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export async function getResearchPlan(payload: {
  job_id: number;
  weekly_hours: number;
  weeks: number;
  goal: "skills" | "project" | "interview";
  learning_style?: "hands_on" | "guided" | "intensive";
  language: "en" | "zh-CN" | "zh-TW";
}): Promise<ResearchPlan> {
  return request<ResearchPlan>("/resources/research-plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export function getSavedResearchPlan(jobId: number): Promise<ResearchPlan> {
  return request<ResearchPlan>(`/resources/research-plans?job_id=${jobId}`);
}
export function updateResearchPlan(
  id: number,
  payload: Pick<
    ResearchPlan,
    "profile_summary" | "gaps" | "method" | "sources"
  >,
): Promise<ResearchPlan> {
  return request(`/resources/research-plans/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export function deleteResearchPlan(id: number): Promise<void> {
  return request(`/resources/research-plans/${id}`, { method: "DELETE" });
}
export async function completeResource(
  id: number,
  completed: boolean,
): Promise<LearningResource> {
  return request<LearningResource>(`/resources/${id}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ completed }),
  });
}

export async function createExperienceDraft(
  resourceId: number,
  reflection: string,
): Promise<Experience> {
  return request<Experience>(`/resources/${resourceId}/experience-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reflection }),
  });
}

export async function checkResourceHealth(
  resourceId: number,
): Promise<LearningResource> {
  return request<LearningResource>(`/resources/${resourceId}/health-check`, {
    method: "POST",
  });
}
export type ResourceFeedbackCategory =
  "broken_link" | "outdated_content" | "other";
export async function submitResourceFeedback(
  resourceId: number,
  category: ResourceFeedbackCategory,
  message: string,
): Promise<{ id: number; message: string }> {
  return request(`/resources/${resourceId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, message }),
  });
}
