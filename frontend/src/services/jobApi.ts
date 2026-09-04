import type {
  ApplicationReadiness,
  Job,
  JobImportDraft,
  MatchReport,
} from "../types/job";
import { request } from "./request";

export async function analyzeJob(payload: {
  title: string;
  company: string;
  description: string;
}): Promise<Job> {
  return request<Job>(`/jobs/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function previewJobAnalysis(payload: {
  title: string;
  company: string;
  description: string;
}): Promise<MatchReport> {
  return request<MatchReport>(`/jobs/analyze-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function previewManualJobAnalysis(payload: {
  title: string;
  company: string;
  job_category: string;
  location: string;
  required_skills: string[];
  responsibilities: string[];
  additional_details: string;
}): Promise<MatchReport> {
  return request<MatchReport>(`/jobs/analyze-manual-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function saveAnalyzedJob(payload: {
  title: string;
  company: string;
  description: string;
  required_skills: string[];
  preferred_skills: string[];
  responsibilities: string[];
  qualifications: string[];
}): Promise<Job> {
  return request<Job>(`/jobs/save-analyzed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getMatchReport(jobId: number): Promise<MatchReport> {
  return request<MatchReport>(`/jobs/${jobId}/match-report`);
}
export async function listJobs(): Promise<Job[]> {
  return request<Job[]>("/jobs");
}
export async function deleteJob(jobId: number): Promise<void> {
  await request<void>(
    `/jobs/${jobId}`,
    { method: "DELETE" },
    { parseJson: false },
  );
}
export async function getApplicationReadiness(
  jobId: number,
): Promise<ApplicationReadiness> {
  return request<ApplicationReadiness>(`/jobs/${jobId}/readiness`);
}

export async function importJobUrl(url: string): Promise<JobImportDraft> {
  return request<JobImportDraft>(`/jobs/import-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export async function importJobScreenshot(
  file: File,
  consent: boolean,
): Promise<JobImportDraft> {
  const form = new FormData();
  form.set("file", file);
  form.set("consent_to_cloud_ocr", String(consent));
  return request<JobImportDraft>(`/jobs/import-screenshot`, {
    method: "POST",
    body: form,
  });
}
