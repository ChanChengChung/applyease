export type ProjectSpec = {
  title: string;
  task: string;
  estimated_days: number;
  deliverables: string[];
  completion_criteria: string[];
  cv_bullet_template: string;
};
export type LearningResource = {
  id: number;
  title: string;
  url: string;
  provider: string;
  skills: string[];
  difficulty: string;
  duration_hours: number;
  free: boolean;
  description: string;
  project: ProjectSpec;
  verified: boolean;
  completed: boolean;
  link_status?: string;
  last_checked_at?: string | null;
  match_score?: number;
  matched_skills?: string[];
  recommendation_reason?: string;
  created_at: string;
};

export type StarterPlan = {
  id: number;
  interest: string;
  focus: string;
  headline: string;
  first_action: string;
  milestones: string[];
  resources: LearningResource[];
  used_fallback: boolean;
  created_at: string;
  updated_at: string;
};
export type ResearchPlan = {
  id: number;
  job_id: number;
  profile_summary: string;
  gaps: string[];
  method: string[];
  sources: Array<{ title: string; url: string }>;
  searched_at: string;
  used_fallback: boolean;
  created_at: string;
  updated_at: string;
};
