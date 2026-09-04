import type { Experience, ExperienceImpact } from "../types/experience";
import { request } from "./request";

export type ExperienceListOptions = {
  query?: string;
  confirmed?: boolean;
  limit?: number;
  offset?: number;
};
export async function listExperiences(
  options: ExperienceListOptions = {},
): Promise<Experience[]> {
  const params = new URLSearchParams();

  if (options.query?.trim()) params.set("query", options.query.trim());

  if (options.confirmed !== undefined)
    params.set("confirmed", String(options.confirmed));

  params.set("limit", String(options.limit ?? 100));

  params.set("offset", String(options.offset ?? 0));

  return request<Experience[]>(`/experiences?${params.toString()}`);
}
export type ExperiencePayload = Omit<
  Experience,
  "id" | "created_at" | "document_id"
>;
export async function createExperience(
  item: ExperiencePayload,
): Promise<Experience> {
  return request<Experience>(`/experiences`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(item),
  });
}
export async function bulkConfirmExperiences(
  ids: number[],
  confirmed = true,
): Promise<{ updated: number; missing_ids: number[] }> {
  return request<{ updated: number; missing_ids: number[] }>(
    `/experiences/bulk-confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, confirmed }),
    },
  );
}
export type DocumentUploadResult = {
  filename: string;
  text_length: number;
  document_id: number;
  duplicate: boolean;
  restored: boolean;
  reused: boolean;
  experiences: Experience[];
};

export async function uploadCV(file: File): Promise<DocumentUploadResult> {
  const body = new FormData();
  body.append("file", file);
  return request<DocumentUploadResult>(`/documents/upload`, {
    method: "POST",
    body,
  });
}
export async function updateExperience(item: Experience): Promise<Experience> {
  const payload = {
    title: item.title.trim(),
    organization: item.organization.trim(),
    description: item.description.trim(),
    skills: item.skills,
    achievements: item.achievements,
    category: item.category,
    confirmed: item.confirmed,
  };

  return request<Experience>(`/experiences/${item.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function replaceExperience(
  id: number,
  item: ExperiencePayload,
): Promise<Experience> {
  return request<Experience>(`/experiences/${id}/replace`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...item, confirmed: false }),
  });
}

export async function deleteExperience(id: number): Promise<void> {
  return request<void>(
    `/experiences/${id}`,
    { method: "DELETE" },
    { parseJson: false },
  );
}

export async function getExperienceImpacts(): Promise<ExperienceImpact[]> {
  return request<ExperienceImpact[]>("/experiences/evidence-impact");
}
