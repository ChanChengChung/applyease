export type SourceCitation = {
  experience_id: number;
  experience_title: string;
  text: string;
  claim?: string;
};
export type OutputLanguage = "en" | "zh-CN" | "zh-TW";
export type AnswerTone =
  | "professional"
  | "concise"
  | "enthusiastic"
  | "technical"
  | "reflective";
export type Material = {
  id: number;
  job_id: number;
  material_type: string;
  text: string;
  character_count: number;
  fact_check_passed: boolean;
  warnings: string[];
  sources: SourceCitation[];
  generation_method: "ai" | "rules" | "user_edited" | string;
  max_characters?: number | null;
  output_language?: OutputLanguage;
  created_at: string;
};
export type ResumeTemplate = "classic" | "modern" | "compact";
export type ResumeFontStyle =
  | "default"
  | "sans"
  | "serif"
  | "microsoft_yahei";
export type ResumeDensity = "relaxed" | "standard" | "compact";
export type ResumeAccent = "template" | "navy" | "black";
export type ResumeAppearance = {
  fontStyle: ResumeFontStyle;
  density: ResumeDensity;
  accent: ResumeAccent;
};
