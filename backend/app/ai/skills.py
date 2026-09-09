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

# Role requirements are not always programming languages. Keep this vocabulary
# separate from ``KNOWN_SKILLS`` so CV parsing does not manufacture a skill
# merely because a phrase appears in prose. These terms are only extracted
# when the job posting itself states them.
JOB_COMPETENCIES: dict[str, tuple[str, ...]] = {
    "Project Management": ("project management",),
    "IT Operations": ("information technology", "IT environment", "IT operations"),
    "Inventory Management": ("inventory management",),
    "Supply Chain": ("supply chain",),
    "Warehouse Management": ("warehouse management",),
    "Logistics": ("logistics",),
    "Stakeholder Management": ("stakeholder management",),
    "Vendor Management": ("vendor management", "third-party vendors"),
    "Process Improvement": ("process improvement", "process optimization", "process optimisation"),
    "Safety Compliance": ("safety procedures", "safety compliance", "safety training"),
}

# Evidence terms are intentionally narrower than a semantic model: every
# derived match still points to exact text in a confirmed experience.
JOB_COMPETENCY_EVIDENCE_TERMS: dict[str, tuple[str, ...]] = {
    "Project Management": ("project management", "planned", "planning", "coordinated", "coordinate", "executed", "led"),
    "IT Operations": ("information technology", "IT", "software", "backend", "frontend", "FastAPI", "PostgreSQL", "React"),
    "Inventory Management": ("inventory management", "inventory control", "inventory"),
    "Supply Chain": ("supply chain", "procurement"),
    "Warehouse Management": ("warehouse management", "warehouse"),
    "Logistics": ("logistics", "logistical"),
    "Stakeholder Management": ("stakeholder", "client communication", "cross-functional"),
    "Vendor Management": ("vendor", "supplier", "third-party"),
    "Process Improvement": ("process improvement", "automation", "optimizing", "optimising", "performance bottleneck", "efficiency"),
    "Safety Compliance": ("safety", "compliance", "PPE"),
}
