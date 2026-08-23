import type { ApplicantProfile } from "../types/applicantProfile";
import { request } from "./request";

export async function getApplicantProfile(): Promise<ApplicantProfile | null> {
  // HTTP 404 means "no profile yet" -> return null instead of throwing.
  return request<ApplicantProfile>(
    `/applicant-profile`,
    {},
    { expectStatus: 404 },
  );
}
export async function saveApplicantProfile(
  display_name: string,
  contact_line: string,
  details: Partial<
    Pick<
      ApplicantProfile,
      "email" | "phone" | "location" | "linkedin_url" | "github_url"
    >
  > = {},
): Promise<ApplicantProfile> {
  return request<ApplicantProfile>(`/applicant-profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name, contact_line, ...details }),
  });
}
export async function deleteApplicantProfile(): Promise<void> {
  return request<void>(
    `/applicant-profile`,
    { method: "DELETE" },
    { parseJson: false },
  );
}
