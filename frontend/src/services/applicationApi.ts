import type {
  AnswerTemplate,
  Application,
  ApplicationQuestion,
  BatchGenerationTask,
  GeneratedAnswer,
} from "../types/application";
import { request } from "./request";

export async function detectQuestions(
  jobId: number,
  rawText: string,
): Promise<Application> {
  return request<Application>(`/applications/questions/detect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, raw_text: rawText }),
  });
}
export function getLatestApplication(jobId: number): Promise<Application> {
  return request<Application>(`/applications/latest?job_id=${jobId}`);
}
export async function createManualQuestion(
  jobId: number,
  question = "",
  options: {
    maxCharacters?: number;
    answerTone?: "professional" | "concise" | "enthusiastic" | "technical" | "reflective";
    desiredContent?: string;
  } = {},
): Promise<Application> {
  return request<Application>(`/applications/questions/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_id: jobId,
      question,
      max_characters: options.maxCharacters,
      answer_tone: options.answerTone,
      desired_content: options.desiredContent,
    }),
  });
}
export async function updateManualQuestion(
  applicationId: number,
  questionId: number,
  payload: {
    question: string;
    maxCharacters?: number;
    answerTone?: "professional" | "concise" | "enthusiastic" | "technical" | "reflective";
    desiredContent?: string;
  },
): Promise<ApplicationQuestion> {
  return request<ApplicationQuestion>(
    `/applications/${applicationId}/questions/${questionId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: payload.question,
        max_characters: payload.maxCharacters,
        answer_tone: payload.answerTone,
        desired_content: payload.desiredContent,
      }),
    },
  );
}
export function getSavedAnswers(
  applicationId: number,
): Promise<GeneratedAnswer[]> {
  return request<GeneratedAnswer[]>(`/applications/${applicationId}/answers`);
}
export async function generateQuestionAnswer(
  applicationId: number,
  questionId: number,
  template: AnswerTemplate = "auto",
  outputLanguage: "en" | "zh-CN" | "zh-TW" = "en",
): Promise<GeneratedAnswer> {
  return request<GeneratedAnswer>(
    `/applications/${applicationId}/questions/${questionId}/answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template, output_language: outputLanguage }),
    },
  );
}
export async function generateAllAnswers(
  applicationId: number,
  regenerate = false,
  template: AnswerTemplate = "auto",
  outputLanguage: "en" | "zh-CN" | "zh-TW" = "en",
): Promise<BatchGenerationTask> {
  return request<BatchGenerationTask>(
    `/applications/${applicationId}/answers/generate-all`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ regenerate, template, output_language: outputLanguage }),
    },
  );
}
export function getBatchGenerationTask(taskId: string): Promise<BatchGenerationTask> {
  return request<BatchGenerationTask>(`/applications/batch-tasks/${taskId}`);
}
export async function updateQuestionAnswer(
  applicationId: number,
  questionId: number,
  answer: string,
): Promise<GeneratedAnswer> {
  return request<GeneratedAnswer>(
    `/applications/${applicationId}/questions/${questionId}/answer`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answer }),
    },
  );
}
export async function detectScreenshot(
  jobId: number,
  file: File,
  consent: boolean,
): Promise<Application> {
  const body = new FormData();
  body.append("job_id", String(jobId));
  body.append("consent_to_cloud_ocr", String(consent));
  body.append("file", file);
  return request<Application>(`/applications/questions/detect-screenshot`, {
    method: "POST",
    body,
  });
}
