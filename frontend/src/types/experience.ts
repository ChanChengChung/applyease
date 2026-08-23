export type Achievement = { text: string; source: string; verified: boolean };
export type ExperienceCategory =
  | "personal"
  | "education"
  | "internship"
  | "leadership"
  | "research"
  | "project";

export type Experience = {
  id: number;
  title: string;
  organization: string;
  description: string;

  skills: string[];
  achievements: Achievement[];
  source_file: string;
  category: ExperienceCategory;

  confirmed: boolean;
  created_at?: string;
};

export type ExperienceImpact = {
  experience_id: number;
  confirmed: boolean;
  skills_available: string[];
  supported_jobs: Array<{
    job_id: number;
    title: string;
    company: string;
    requirements_supported: number;
  }>;
  material_references: Array<{
    material_id: number;
    job_id: number;
    material_type: string;
  }>;
};
