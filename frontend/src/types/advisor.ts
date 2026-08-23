export type AdvisorMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  suggested_prompts?: string[];
  used_fallback?: boolean;
};
export type AdvisorReply = {
  answer: string;
  sources: string[];
  suggested_prompts: string[];
  used_fallback: boolean;
};
export type AdvisorContext = {
  activePage: string;
  activeJobId?: number;
};
export type SavedAdvisorMessage = AdvisorMessage & {
  id: number;
  created_at: string;
};
