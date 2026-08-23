export type Job = {
  id: number;
  title: string;
  company: string;
  description: string;

  required_skills: string[];
  preferred_skills: string[];

  responsibilities: string[];
  qualifications: string[];
  created_at: string;
};
export type JobImportDraft = {
  title: string;
  company: string;
  description: string;
  location: string;
  deadline: string;
  source_url: string;
};
export type Evidence = {
  requirement: string;
  experience_id: number;
  experience_title: string;
  evidence: string;
};
export type MatchReport = {
  job: Job;
  overall_score: number;
  matched_skills: string[];
  missing_skills: string[];
  evidence: Evidence[];
  considered_experience_ids: number[];

  matched_required_skills?: string[];
  missing_required_skills?: string[];

  matched_preferred_skills?: string[];
  missing_preferred_skills?: string[];

  score_breakdown?: Record<string, number>;
  warnings?: string[];
};

export type ApplicationReadiness = {
  job_id: number;
  ready_to_submit: boolean;
  blockers: number;
  warnings: number;
  match_score: number;
  missing_required_skills: string[];
  items: {
    code: string;
    severity: "pass" | "warning" | "blocker";
    title: string;
    detail: string;
    target: string;
    params?: Record<string, unknown>;
  }[];
  verdict?: "ready" | "review" | "prepare" | "hold";
  verdict_reason?: string;
  verdict_reason_code?: string;
  verdict_reason_params?: Record<string, unknown>;
  primary_action?: {
    code: string;
    severity: string;
    title: string;
    detail: string;
    target: string;
    params?: Record<string, unknown>;
  } | null;
};
