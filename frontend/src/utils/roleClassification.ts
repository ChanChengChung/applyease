export type OpportunityFolderKey =
  | "education_training"
  | "finance"
  | "engineering"
  | "data_ai"
  | "consulting"
  | "marketing_sales"
  | "operations"
  | "education_research"
  | "healthcare"
  | "legal_public"
  | "other";

export const OPPORTUNITY_FOLDER_KEYS: OpportunityFolderKey[] = [
  "education_training",
  "finance",
  "engineering",
  "data_ai",
  "consulting",
  "marketing_sales",
  "operations",
  "education_research",
  "healthcare",
  "legal_public",
  "other",
];

// Keep category vocabulary in one place so the discovery selector, role
// library and saved-job library cannot drift apart. Generic terms such as
// “analyst” are intentionally excluded: they are not a job category by
// themselves and otherwise steal finance roles into data/AI.
const FOLDER_TERMS: Record<OpportunityFolderKey, string[]> = {
  education_training: ["education", "teacher", "teaching", "training", "academic", "学校", "教师", "教育", "培训", "教学"],
  finance: ["bank", "banking", "finance", "financial", "investment", "trading", "quant", "quantitative", "accounting", "actuarial", "treasury", "risk", "金融", "银行", "交易", "投资"],
  engineering: ["engineer", "engineering", "software", "developer", "development", "programmer", "programming", "compiler", "hardware", "mechanical", "electrical", "civil", "manufacturing", "工程", "机械", "电气"],
  data_ai: ["data", "analytics", "data scientist", "machine learning", "artificial intelligence", "algorithm", " ai", "数据", "算法", "人工智能"],
  consulting: ["consult", "strategy", "advisory", "咨询", "战略"],
  marketing_sales: ["marketing", "sales", "brand", "communications", "business development", "市场", "销售", "商务"],
  operations: ["operations", "program", "project manager", "supply chain", "customer", "human resources", " hr", "运营", "项目管理", "人力"],
  education_research: ["research", "scientist", "研究", "科学"],
  healthcare: ["health", "medical", "clinical", "pharma", "biotech", "healthcare", "医疗", "医药"],
  legal_public: ["legal", "law", "compliance", "policy", "government", "public affairs", "法律", "合规", "政府"],
  other: [],
};

/** Classify a role with title terms weighted above company/location metadata. */
export function classifyRole(
  title: string,
  company = "",
  employmentType = "",
  location = "",
): OpportunityFolderKey {
  const titleText = title.trim().toLowerCase();
  const allText = `${title} ${company} ${employmentType} ${location}`.trim().toLowerCase();
  const hasTerm = (text: string, term: string) => {
    const normalized = term.trim().toLowerCase();
    if (!normalized) return false;
    // Word boundaries prevent false positives such as “data” in “candidate”
    // or “ai” in an unrelated word; CJK terms remain substring matches.
    if (/^[a-z0-9 ]+$/.test(normalized)) {
      return new RegExp(`(^|[^a-z0-9])${normalized.replace(/ /g, "\\s+")}(?=$|[^a-z0-9])`, "i").test(text);
    }
    return text.includes(normalized);
  };
  let best: OpportunityFolderKey = "other";
  let bestScore = 0;
  OPPORTUNITY_FOLDER_KEYS.forEach((folder) => {
    if (folder === "other") return;
    const score = FOLDER_TERMS[folder].reduce((sum, term) => {
      if (!hasTerm(allText, term)) return sum;
      return sum + (hasTerm(titleText, term) ? 10 : 1);
    }, 0);
    if (score > bestScore) {
      best = folder;
      bestScore = score;
    }
  });
  return best;
}
