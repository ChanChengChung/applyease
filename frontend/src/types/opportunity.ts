export type OpportunitySource = { title: string; url: string };

export type OpportunityMatch = {
  company: string;
  title: string;
  location: string;
  employment_type: string;
  why_match: string;
  evidence_used: string[];
  gaps_to_address: string[];
  next_step: string;
  source_search_mode?: "ai" | "official_ats";
  source_title: string;
  source_url: string;
};

export type OpportunitySearch = {
  id: number;
  career_goal: string;
  location: string;
  work_preference: "any" | "onsite" | "hybrid" | "remote";
  timing: string;
  language: "en" | "zh-CN" | "zh-TW";
  search_modes: Array<"ai" | "official_ats">;
  experience_ids: number[];
  opportunities: OpportunityMatch[];
  sources: OpportunitySource[];
  used_fallback: boolean;
  unavailable_reason?:
    "" | "quota_exhausted" | "provider_unavailable" | "ats_fallback";
  strategy_outcomes: Array<{
    mode: "ai" | "official_ats";
    status: "success" | "failed" | "quota_exhausted";
    count: number;
  }>;
  created_at: string;
};

export type OpportunitySearchPayload = {
  career_goal: string;
  location: string;
  work_preference: "any" | "onsite" | "hybrid" | "remote";
  timing: string;
  language: "en" | "zh-CN" | "zh-TW";
  search_modes: Array<"ai" | "official_ats">;
  experience_ids: number[];
  consent_to_web_search: boolean;
  limit: number;
};
