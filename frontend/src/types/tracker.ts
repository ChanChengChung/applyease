export type TrackerStatus =
  | "saved"
  | "applied"
  | "assessment"
  | "interview"
  | "offer"
  | "rejected"
  | "withdrawn";
export type TrackedApplication = {
  id: number;
  company: string;
  role: string;
  job_id?: number;
  deadline?: string;
  status: TrackerStatus;
  interview_date?: string;
  follow_up_at?: string;
  notes: string;
  created_at: string;
  is_overdue?: boolean;
  is_follow_up_due?: boolean;
  next_action?: string;
};
export type TrackerSummary = {
  total: number;
  by_status: Record<string, number>;
  active: number;
  overdue: number;
  follow_ups_due: number;
  next_action?: TrackedApplication;
};
export type TrackerReminderKind = "deadline" | "follow_up" | "interview";
export type TrackerReminderState = "overdue" | "today" | "upcoming";
export type TrackerReminder = {
  application_id: number;
  kind: TrackerReminderKind;
  due_date: string;
  state: TrackerReminderState;
  company: string;
  role: string;
  title: string;
};
export type ApplicationWorkspace = {
  application_id: number;
  job_id?: number;
  match_score?: number;
  evidence_count: number;
  missing_skills: string[];
  material_types: string[];
  questions_total: number;
  answers_ready: number;
  learning_plan_id?: number | null;
  learning_plan_steps?: number;
  learning_plan_sources?: number;
  learning_plan_updated_at?: string | null;
  application_status: TrackerStatus;
  material_versions: MaterialVersion[];
};
export type MaterialVersion = {
  id: number;
  material_type: string;
  generation_method: string;
  created_at: string;
  fact_check_passed: boolean;
  source_count: number;
};
