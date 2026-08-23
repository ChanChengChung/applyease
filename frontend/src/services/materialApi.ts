import type {
  Material,
  AnswerTone,
  OutputLanguage,
  ResumeAppearance,
  ResumeTemplate,
} from "../types/material";
import { request, ApiRequestError } from "./request";

/** POST with an optional JSON payload (skips Content-Type/body when payload is absent). */
async function postJson<T>(path: string, payload?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: payload ? { "Content-Type": "application/json" } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });
}

export const generateResume = (
  jobId: number,
  outputLanguage: OutputLanguage = "en",
) =>
  postJson<Material>(
    `/materials/resume/generate?job_id=${jobId}&output_language=${encodeURIComponent(outputLanguage)}`,
  );
export const generateCoverLetter = (
  jobId: number,
  outputLanguage: OutputLanguage = "en",
) =>
  postJson<Material>(
    `/materials/cover-letter/generate?job_id=${jobId}&output_language=${encodeURIComponent(outputLanguage)}`,
  );
export const generateAnswer = (
  jobId: number,
  question: string,
  max_characters: number,
  outputLanguage: OutputLanguage = "en",
  preferences: { tone: AnswerTone; desiredContent: string } = {
    tone: "professional",
    desiredContent: "",
  },
) =>
  postJson<Material>(`/materials/answer/generate?job_id=${jobId}`, {
    question,
    max_characters,
    output_language: outputLanguage,
    answer_tone: preferences.tone,
    desired_content: preferences.desiredContent,
  });
export const listMaterials = (jobId: number) =>
  request<Material[]>(`/materials?job_id=${jobId}`);
export const updateMaterial = (materialId: number, text: string) =>
  request<Material>(`/materials/${materialId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

/**
 * Export a material as a downloadable file. Unlike the other helpers this
 * returns a Blob (not parsed JSON), so we call fetch directly and wrap errors
 * with the shared ApiRequestError via request() on the metadata-less path.
 */
export async function downloadResume(
  materialId: number,
  format: "docx" | "pdf",
  template: ResumeTemplate,
  includeSources: boolean,
  displayName: string,
  contactLine: string,
  contactDetails:
    | {
        email?: string;
        phone?: string;
        location?: string;
        linkedin_url?: string;
        github_url?: string;
      }
    | string[] = {},
  sectionOrder: string[] = [],
  hiddenSections: string[] = [],
  appearance?: ResumeAppearance,
): Promise<{ blob: Blob; filename: string }> {
  // Preserve the former positional signature for callers on an older UI
  // bundle: (.., contactLine, sectionOrder, hiddenSections).
  if (Array.isArray(contactDetails)) {
    hiddenSections = sectionOrder;
    sectionOrder = contactDetails;
    contactDetails = {};
  }
  const apiBase = (
    import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1"
  ).replace(/\/$/, "");
  const response = await fetch(`${apiBase}/materials/${materialId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      format,
      template,
      include_sources: includeSources,
      display_name: displayName,
      contact_line: contactLine,
      ...contactDetails,
      section_order: sectionOrder,
      hidden_sections: hiddenSections,
      ...(appearance
        ? {
            font_style: appearance.fontStyle,
            density: appearance.density,
            accent: appearance.accent,
          }
        : {}),
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    // Re-throw using the shared error type so callers handle it uniformly.
    throw new ApiRequestError(response.status, error.detail);
  }

  const disposition = response.headers.get("Content-Disposition") || "";
  const filename =
    disposition.match(/filename="?([^";]+)"?/i)?.[1] ||
    `ApplyEase-resume.${format}`;
  return { blob: await response.blob(), filename };
}

export function saveDownload({
  blob,
  filename,
}: {
  blob: Blob;
  filename: string;
}) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
