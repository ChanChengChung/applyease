export type DetectedField = { field_id: string; label: string; name: string; html_id: string; placeholder: string; input_type: string; max_characters?: number; options: string[] };
export type PreviewItem = { field_id: string; label: string; status: string; answer: string; question_id?: number; question: string; warnings: string[]; source_ids: number[] };
