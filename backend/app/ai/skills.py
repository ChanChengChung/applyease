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
]
