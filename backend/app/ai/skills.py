"""Shared skill vocabulary for CV parsing, job analysis and matching.

Historically two independent KNOWN_SKILLS lists drifted apart: the CV parser
recognised 20 skills while job analysis recognised 31.  The gap produced a
silent inconsistency -- a CV mentioning "Market Making" could not attach that
skill to an experience, yet a job requiring it was reported as an unmet gap.

Every module that needs a fixed skill vocabulary imports the single list here.
LLM-backed extraction does not depend on this whitelist; it is only the
deterministic fallback vocabulary.
"""

# Keep this list ordered the way job analysis originally ordered it so the
# deterministic matching behaviour is unchanged for skills both lists shared.
KNOWN_SKILLS = [
    "Python",
    "OCaml",
    "Java",
    "Go",
    "Rust",
    "C#",
    "Scala",
    "Kotlin",
    "SQL",
    "TypeScript",
    "JavaScript",
    "React",
    "FastAPI",
    "PostgreSQL",
    "PyTorch",
    "C++",
    "Docker",
    "Machine Learning",
    "Deep Learning",
    "Transformer",
    "Pandas",
    "NumPy",
    "Git",
    "RNN",
    "Reinforcement Learning",
    "MATLAB",
    "C",
    "Statistics",
    "Probability",
    "Linear Algebra",
    "Risk Management",
    "Quantitative Research",
    "Market Making",
    "Algorithms",
    "Data Structures",
    "NLP",
    "Computer Vision",
    "REST APIs",
    "Linux",
    "Kubernetes",
    "AWS",
]

# These phrases are useful tags for discovery and resource search, but they
# describe a career domain rather than a concrete, independently verifiable
# technical skill.  Job matching must not turn a sentence such as
# "Python is required for quantitative research" into a fake missing
# "Quantitative Research" skill gap.
CAREER_DOMAIN_TERMS = {
    "Quantitative Research",
    "Market Making",
}

JOB_SKILLS = [skill for skill in KNOWN_SKILLS if skill not in CAREER_DOMAIN_TERMS]

# A requirement may appear in English, Simplified Chinese or Traditional
# Chinese.  Aliases only identify an explicitly stated requirement; they never
# create a CV skill by inference.  This keeps the deterministic fallback both
# multilingual and reviewable.
JOB_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("Python", "蟒蛇语言"),
    "OCaml": ("OCaml",),
    "Java": ("Java",),
    "Go": ("Go", "Golang"),
    "Rust": ("Rust",),
    "C#": ("C#",),
    "Scala": ("Scala",),
    "Kotlin": ("Kotlin",),
    "SQL": ("SQL", "结构化查询语言", "結構化查詢語言"),
    "TypeScript": ("TypeScript",),
    "JavaScript": ("JavaScript",),
    "React": ("React",),
    "FastAPI": ("FastAPI",),
    "PostgreSQL": ("PostgreSQL",),
    "PyTorch": ("PyTorch",),
    "C++": ("C++",),
    "Docker": ("Docker", "容器化", "容器化"),
    "Machine Learning": ("machine learning", "机器学习", "機器學習"),
    "Deep Learning": ("deep learning", "深度学习", "深度學習"),
    "Transformer": ("transformer", "转换器模型", "轉換器模型"),
    "Pandas": ("Pandas",),
    "NumPy": ("NumPy",),
    "Git": ("Git", "版本控制", "版本控制"),
    "Reinforcement Learning": ("reinforcement learning", "强化学习", "強化學習"),
    "MATLAB": ("MATLAB",),
    "Statistics": ("statistics", "统计", "統計"),
    "Probability": ("probability", "概率", "機率"),
    "Linear Algebra": ("linear algebra", "线性代数", "線性代數"),
    "Risk Management": ("risk management", "风险管理", "風險管理"),
    "Algorithms": ("algorithms", "算法", "演算法"),
    "Data Structures": ("data structures", "数据结构", "資料結構"),
    "NLP": ("NLP", "natural language processing", "自然语言处理", "自然語言處理"),
    "Computer Vision": ("computer vision", "计算机视觉", "電腦視覺"),
    "REST APIs": ("REST API", "REST APIs", "接口开发", "介面開發"),
    "Linux": ("Linux",),
    "Kubernetes": ("Kubernetes", "K8s"),
    "AWS": ("AWS", "Amazon Web Services"),
}

# Each catalogue entry has: (1) the words a posting must explicitly contain,
# and (2) the narrower, auditable words that can support it in an experience.
# Categories match the Opportunity Hub folders, so adding a new industry does
# not silently change matching rules for every other industry.
ROLE_COMPETENCY_CATALOG: dict[str, dict[str, dict[str, tuple[str, ...]]]] = {
    "shared": {
        "Project Management": {
            "posting": ("project management", "项目管理", "專案管理"),
            "evidence": ("project management", "planned", "planning", "coordinated", "executed", "led", "项目管理", "规划", "規劃", "协调", "協調", "执行", "執行", "领导", "領導"),
        },
        "Stakeholder Management": {
            "posting": ("stakeholder management", "stakeholders", "利益相关者管理", "利害關係人管理"),
            "evidence": ("stakeholder", "client communication", "cross-functional", "利益相关者", "利害關係人", "跨部门", "跨部門", "客户沟通", "客戶溝通"),
        },
        "Process Improvement": {
            "posting": ("process improvement", "process optimization", "process optimisation", "流程优化", "流程優化"),
            "evidence": ("process improvement", "automation", "optimizing", "optimising", "efficiency", "流程优化", "流程優化", "自动化", "自動化", "效率"),
        },
    },
    "engineering": {
        "IT Operations": {
            "posting": ("information technology", "IT environment", "IT operations", "信息技术", "資訊科技", "IT 环境", "IT 環境", "IT 运维", "IT 維運"),
            "evidence": ("information technology", "IT", "software", "backend", "frontend", "FastAPI", "PostgreSQL", "React", "信息技术", "資訊科技", "后端", "後端", "前端", "软件", "軟體"),
        },
        "Systems Engineering": {
            "posting": ("systems engineering", "distributed systems", "系统工程", "系統工程", "分布式系统", "分散式系統"),
            "evidence": ("systems engineering", "distributed systems", "microservice", "backend", "系统工程", "系統工程", "分布式系统", "分散式系統", "微服务", "微服務"),
        },
    },
    "data_ai": {
        "Data Analysis": {
            "posting": ("data analysis", "data analytics", "数据分析", "資料分析"),
            "evidence": ("data analysis", "data analytics", "Pandas", "NumPy", "SQL", "数据分析", "資料分析", "数据清洗", "資料清理"),
        },
        "Machine Learning": {
            "posting": ("machine learning", "机器学习", "機器學習"),
            "evidence": ("machine learning", "PyTorch", "model training", "机器学习", "機器學習", "模型训练", "模型訓練"),
        },
    },
    "finance": {
        "Financial Modeling": {
            "posting": ("financial modeling", "financial model", "财务建模", "財務建模"),
            "evidence": ("financial modeling", "valuation", "Excel", "financial statements", "财务建模", "財務建模", "估值", "财务报表", "財務報表"),
        },
        "Market Analysis": {
            "posting": ("market analysis", "investment research", "市场分析", "市場分析", "投资研究", "投資研究"),
            "evidence": ("market analysis", "investment research", "market data", "市场分析", "市場分析", "投资研究", "投資研究", "市场数据", "市場數據"),
        },
    },
    "operations": {
        "Inventory Management": {
            "posting": ("inventory management", "inventory control", "库存管理", "庫存管理", "存货管理", "存貨管理"),
            "evidence": ("inventory management", "inventory control", "inventory", "库存管理", "庫存管理", "盘点", "盤點"),
        },
        "Supply Chain": {
            "posting": ("supply chain", "供应链", "供應鏈"),
            "evidence": ("supply chain", "procurement", "供应链", "供應鏈", "采购", "採購"),
        },
        "Warehouse Management": {
            "posting": ("warehouse management", "warehouse", "仓储管理", "倉儲管理", "仓库", "倉庫"),
            "evidence": ("warehouse management", "warehouse", "仓储", "倉儲", "仓库", "倉庫"),
        },
        "Logistics": {
            "posting": ("logistics", "logistical", "物流"),
            "evidence": ("logistics", "logistical", "物流", "配送", "运输", "運輸"),
        },
        "Vendor Management": {
            "posting": ("vendor management", "third-party vendors", "供应商管理", "供應商管理"),
            "evidence": ("vendor", "supplier", "third-party", "供应商", "供應商", "第三方"),
        },
        "Safety Compliance": {
            "posting": ("safety procedures", "safety compliance", "safety training", "安全流程", "安全程序", "安全合规", "安全合規", "安全培训", "安全培訓"),
            "evidence": ("safety", "compliance", "PPE", "安全", "合规", "合規", "防护装备", "防護裝備"),
        },
    },
    "consulting": {
        "Client Advisory": {"posting": ("client advisory", "client service", "客户咨询", "客戶諮詢", "客户服务", "客戶服務"), "evidence": ("client advisory", "client service", "client presentation", "客户", "客戶", "咨询", "諮詢", "汇报", "匯報")},
    },
    "marketing_sales": {
        "Campaign Management": {"posting": ("campaign management", "marketing campaign", "营销活动", "行銷活動", "市场推广", "市場推廣"), "evidence": ("campaign management", "marketing campaign", "audience growth", "营销", "行銷", "推广", "推廣", "活动策划", "活動策劃")},
    },
    "education_training": {
        "Curriculum Design": {"posting": ("curriculum design", "instructional design", "课程设计", "課程設計", "教学设计", "教學設計"), "evidence": ("curriculum design", "lesson plan", "teaching", "课程设计", "課程設計", "教案", "教学", "教學")},
    },
    "education_research": {
        "Academic Research": {"posting": ("academic research", "research methodology", "学术研究", "學術研究", "研究方法"), "evidence": ("academic research", "literature review", "research project", "学术研究", "學術研究", "文献综述", "文獻綜述", "研究项目", "研究項目")},
    },
    "healthcare": {
        "Clinical Operations": {"posting": ("clinical operations", "patient care", "临床运营", "臨床營運", "患者护理", "病人護理"), "evidence": ("clinical operations", "patient care", "clinical", "临床", "臨床", "患者", "病人")},
    },
    "legal_public": {
        "Policy Analysis": {"posting": ("policy analysis", "public policy", "政策分析", "公共政策"), "evidence": ("policy analysis", "public policy", "regulation", "政策分析", "公共政策", "法规", "法規")},
    },
}

JOB_COMPETENCIES: dict[str, tuple[str, ...]] = {
    name: item["posting"]
    for category in ROLE_COMPETENCY_CATALOG.values()
    for name, item in category.items()
}
JOB_COMPETENCY_EVIDENCE_TERMS: dict[str, tuple[str, ...]] = {
    name: item["evidence"]
    for category in ROLE_COMPETENCY_CATALOG.values()
    for name, item in category.items()
}


def applicable_job_competencies(text: str) -> dict[str, tuple[str, ...]]:
    """Return shared plus industries explicitly signalled by this posting.

    A role can span several industries (for example, data operations).  We
    therefore never force one opaque classifier result; a category becomes
    applicable only when one of its own posting terms occurs in the text.
    """
    lower = text.casefold()
    selected = dict(ROLE_COMPETENCY_CATALOG["shared"])
    for category, competencies in ROLE_COMPETENCY_CATALOG.items():
        if category == "shared":
            continue
        if any(term.casefold() in lower for item in competencies.values() for term in item["posting"]):
            selected.update(competencies)
    return {name: item["posting"] for name, item in selected.items()}
