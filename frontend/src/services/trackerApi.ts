import type {
  TrackedApplication,
  TrackerReminder,
  TrackerStatus,
  TrackerSummary,
  ApplicationWorkspace,
  InterviewReview,
} from "../types/tracker";
import { ApiRequestError, request } from "./request";

export type TrackerListOptions = {
  status?: TrackerStatus;
  from_date?: string;
  to_date?: string;
  sort?: "deadline" | "created_at" | "follow_up";
};
export type TrackerPayload = {
  company?: string;
  role?: string;
  job_id?: number | null;
  deadline?: string | null;
  status?: TrackerStatus;
  interview_date?: string | null;
  follow_up_at?: string | null;
  notes?: string | null;
  interview_review?: InterviewReview | null;
};
export type InterviewReviewCoachPayload = {
  questions: string;
  strengths: string;
  improvements: string;
  next_steps: string;
  output_language?: "en" | "zh-CN" | "zh-TW";
};

export async function listTracked(
  options: TrackerListOptions = {},
): Promise<TrackedApplication[]> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.from_date) params.set("from_date", options.from_date);
  if (options.to_date) params.set("to_date", options.to_date);
  if (options.sort) params.set("sort", options.sort);
  return request<TrackedApplication[]>(
    `/tracker/applications?${params.toString()}`,
  );
}
export async function getTrackerSummary(): Promise<TrackerSummary> {
  return request<TrackerSummary>(`/tracker/applications/summary`);
}
export async function getTrackerReminders(
  days = 14,
): Promise<TrackerReminder[]> {
  return request<TrackerReminder[]>(
    `/tracker/applications/reminders?days=${days}`,
  );
}
export async function getApplicationWorkspace(
  id: number,
): Promise<ApplicationWorkspace> {
  return request<ApplicationWorkspace>(`/tracker/applications/${id}/workspace`);
}
export async function createTracked(
  payload: TrackerPayload,
): Promise<TrackedApplication> {
  return request<TrackedApplication>(`/tracker/applications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export async function updateTracked(
  id: number,
  payload: TrackerPayload,
): Promise<TrackedApplication> {
  return request<TrackedApplication>(`/tracker/applications/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
export async function coachInterviewReview(
  id: number,
  payload: InterviewReviewCoachPayload,
): Promise<TrackedApplication> {
  return request<TrackedApplication>(
    `/tracker/applications/${id}/interview-review/coach`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}
export async function deleteTracked(id: number): Promise<void> {
  return request<void>(
    `/tracker/applications/${id}`,
    { method: "DELETE" },
    { parseJson: false },
  );
}

export async function downloadTrackerCalendar(
  id: number,
): Promise<{ blob: Blob; filename: string }> {
  const base = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";
  const response = await fetch(`${base}/tracker/applications/${id}/calendar`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiRequestError(response.status, error.detail);
  }
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename =
    disposition.match(/filename=\"?([^\";]+)\"?/i)?.[1] ||
    "ApplyEase-reminders.ics";
  return { blob: await response.blob(), filename };
}

export function saveCalendarDownload({
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
