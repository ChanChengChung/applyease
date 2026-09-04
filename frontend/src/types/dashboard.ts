export type PageId =
  | "welcome"
  | "dashboard"
  | "profile"
  | "jobs"
  | "opportunities"
  | "builder"
  | "form"
  | "resources"
  | "tracker"
  | "ai-quality"
  | "security";
export type NavigationJob = { id: number; title: string; company: string };
export type DashboardStep = {
  key: string;
  label: string;
  description: string;
  status: "complete" | "current" | "pending";
  target: PageId;
};
export type DashboardDeadline = {
  id: number;
  job_id?: number | null;
  company: string;
  role: string;
  deadline: string;
  status: string;
  kind?: "deadline" | "follow_up" | "interview";
  is_overdue?: boolean;
};
export type DashboardSummary = {
  experience_total: number;
  confirmed_experiences: number;
  pending_experiences: number;

  job_total: number;
  latest_job: NavigationJob | null;
  material_count: number;
  material_types: string[];
  latest_material_type: string | null;

  application_id: number | null;
  questions_total: number;
  answers_ready: number;

  tracker_total: number;
  active_applications: number;
  urgent_deadlines_count?: number;
  upcoming_deadlines: DashboardDeadline[];

  steps: DashboardStep[];
  next_action: { title: string; description: string; target: PageId };
  job_workspaces?: Array<
    NavigationJob & {
      match_score: number;
      evidence_count: number;
      missing_skills: string[];
      material_count: number;
      answers_ready: number;
      questions_total: number;
      tracker_status?: string | null;
      next_target: PageId;
      progress: number;
      steps: DashboardStep[];
    }
  >;
};
