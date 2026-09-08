"""Canonical, deterministic role-folder classification for opportunity results.

Titles are the strongest signal. Company, employment type and location are only
fallback context, so words such as ``research`` cannot misclassify a software
engineering role. English terms use word boundaries to avoid substring matches.
"""

from __future__ import annotations

import re
from typing import Literal

RoleFolder = Literal[
    "education_training", "finance", "engineering", "data_ai", "consulting",
    "marketing_sales", "operations", "education_research", "healthcare",
    "legal_public", "other",
]

FOLDER_TERMS: dict[RoleFolder, tuple[str, ...]] = {
    "education_training": ("education", "teacher", "teaching", "training", "academic", "学校", "教师", "教育", "培训", "教学"),
    "finance": ("bank", "banking", "finance", "financial", "investment", "trading", "quant", "quantitative", "accounting", "actuarial", "treasury", "risk", "金融", "银行", "交易", "投资"),
    "engineering": ("engineer", "engineering", "software", "developer", "development", "programmer", "programming", "compiler", "hardware", "mechanical", "electrical", "civil", "manufacturing", "工程", "机械", "电气"),
    "data_ai": ("data", "analytics", "data scientist", "machine learning", "artificial intelligence", "algorithm", "ai", "数据", "算法", "人工智能"),
    "consulting": ("consult", "strategy", "advisory", "咨询", "战略"),
    "marketing_sales": ("marketing", "sales", "brand", "communications", "business development", "市场", "销售", "商务"),
    "operations": ("operations", "program", "project manager", "supply chain", "customer", "human resources", "hr", "运营", "项目管理", "人力"),
    "education_research": ("research", "scientist", "研究", "科学"),
    "healthcare": ("health", "medical", "clinical", "pharma", "biotech", "healthcare", "医疗", "医药"),
    "legal_public": ("legal", "law", "compliance", "policy", "government", "public affairs", "法律", "合规", "政府"),
    "other": (),
}


def _has_term(text: str, term: str) -> bool:
    term = term.casefold().strip()
    if not term:
        return False
    if re.fullmatch(r"[a-z0-9 ]+", term):
        pattern = re.escape(term).replace(r"\ ", r"\s+")
        return bool(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text.casefold()))
    return term in text.casefold()


def classify_role(title: str, company: str = "", employment_type: str = "", location: str = "") -> RoleFolder:
    title_text = title.strip().casefold()
    all_text = f"{title} {company} {employment_type} {location}".strip().casefold()
    best: RoleFolder = "other"
    best_score = 0
    for folder, terms in FOLDER_TERMS.items():
        if folder == "other":
            continue
        score = sum(10 if _has_term(title_text, term) else 1 for term in terms if _has_term(all_text, term))
        if score > best_score:
            best, best_score = folder, score
    return best
