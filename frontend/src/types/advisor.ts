export type AdvisorMessage = {
  role: "user" | "assistant";
  content: string;
  summary?: string;
  sources?: string[];
  evidence?: AdvisorEvidence[];
  gaps?: string[];
  next_actions?: AdvisorAction[];
  suggested_prompts?: string[];
  used_fallback?: boolean;
  mode?: "ai" | "fallback";
};
export type AdvisorEvidence = {
  type: "experience" | "job" | "material" | "tracker";
  id?: number | null;
  label: string;
  detail?: string;
  target_page?: "profile" | "jobs" | "builder" | "tracker" | null;
};
export type AdvisorAction = {
  label: string;
  target_page: "profile" | "jobs" | "builder" | "form" | "resources" | "tracker";
  target_id?: number | null;
};
export type AdvisorReply = {
  answer: string;
  summary?: string;
  sources: string[];
  evidence?: AdvisorEvidence[];
  gaps?: string[];
  next_actions?: AdvisorAction[];
  suggested_prompts: string[];
  used_fallback: boolean;
  mode?: "ai" | "fallback";
};
export type AdvisorContext = {
  activePage: string;
  activeJobId?: number;
};
export type SavedAdvisorMessage = AdvisorMessage & {
  id: number;
  created_at: string;
};
