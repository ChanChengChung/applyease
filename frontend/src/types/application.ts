export type QuestionMetadata = {
  field_key?: string;
  input_type?: string;
  sensitive?: boolean;
  requires_user_input?: boolean;
  limit_unit?: "characters" | "words";
  max_words?: number | null;
};
export type ApplicationQuestion = {
  id: number;
  application_id: number;
  question: string;
  question_type: string;
  max_characters: number;
  required: boolean;
  answer: {
    metadata?: QuestionMetadata;
    result?: Record<string, unknown>;
    status?: string;
  };
  created_at: string;
};
export type Application = {
  id: number;
  job_id: number;
  raw_text: string;
  questions: ApplicationQuestion[];
  created_at: string;
};
export type AnswerTemplate =
  "auto" | "concise_50" | "standard_150" | "detailed_300" | "star";
export type EffectiveAnswerTemplate = Exclude<AnswerTemplate, "auto">;
export type GeneratedAnswer = {
  question_id: number;
  question: string;
  answer: string;
  character_count: number;
  max_characters: number;
  fact_check_passed: boolean;
  warnings: string[];
  sources: {
    experience_id: number;
    experience_title: string;
    text: string;
    claim?: string;
  }[];
  status: "generated" | "manual_required" | "user_provided" | string;
  generation_method: string;
  word_count: number;
  max_words?: number | null;
  template?: EffectiveAnswerTemplate | null;
  recommended_template?: EffectiveAnswerTemplate | null;
  template_target_characters?: number | null;
  structure_warnings?: string[];
};
