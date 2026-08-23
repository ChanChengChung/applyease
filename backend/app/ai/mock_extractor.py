import re

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
]
SECTION_RE = re.compile(
    r"^(PERSONAL SKILLS|EDUCATION|ENTREPRENEURSHIP.*|.*WORK(?:ING)? EXPERIENCE|(?:WORK|INTERNSHIP|EMPLOYMENT).*|QUANT INSIGHT EXPERIENCE|RESEARCH EXPERIENCE|LEADERSHIP.*|PROJECTS?|COMPETITION.*|ACTIVITIES|EXTRACURRICULAR.*|VOLUNTEER.*)\s*$",
    re.I,
)
DATE_RE = re.compile(r"(?:\d{2}/\d{4}|\d{4}\s*[–-]\s*\d{2}/\d{4}|\bpresent\b|\bexpected\b)", re.I)
BULLET_RE = re.compile(r"^[\-•●▪\uf0b7\uf06c\uf020]")


def _clean(line: str) -> str:
    line = line.replace("\uf0b7", "").replace("\uf06c", "").replace("\uf020", "")

    return re.sub(r"\s+", " ", line.strip(" -•●▪\t"))


def _skills(text: str) -> list[str]:

    return [
        skill
        for skill in KNOWN_SKILLS
        if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", text, re.I)
    ]


def _category_for_section(section: str) -> str:
    section = section.casefold()
    if "education" in section:
        return "education"
    if "research" in section:
        return "research"
    if any(
        word in section
        for word in ("leadership", "entrepreneurship", "activities", "extracurricular", "volunteer")
    ):
        return "leadership"
    if any(word in section for word in ("work", "internship", "employment", "quant insight")):
        return "internship"
    return "project"


def _record(
    title: str, organization: str, body: list[str], source_file: str, category: str = "project"
) -> dict:
    body = [line for line in body if line]

    joined = "\n".join(body)

    achievements = [
        {"text": line, "source": source_file, "verified": False}
        for line in body
        if re.search(
            r"\b\d+(?:\.\d+)?[%+]?|rank|award|increased|reduced|improved|won|selected|scholarship",
            line,
            re.I,
        )
    ]

    return {
        "title": title or "Uncategorized Experience",
        "organization": organization,
        "description": "\n".join(body[:16]),
        "skills": _skills(joined),
        "achievements": achievements[:10],
        "source_file": source_file,
        "category": category,
        "confirmed": False,
    }


def _split_section(section: str, lines: list[str], source_file: str) -> list[dict]:

    if section == "PERSONAL SKILLS":

        return []
    # For education, keep the university and its details as one record.

    if section == "EDUCATION":
        title = next(
            (line for line in lines if "university" in line.lower() or "college" in line.lower()),
            section,
        )

        return [
            _record(
                title,
                "",
                lines[lines.index(title) + 1 :] if title in lines else lines,
                source_file,
                "education",
            )
        ]

    starts = [
        i for i, line in enumerate(lines) if not BULLET_RE.match(line) and DATE_RE.search(line)
    ]

    records: list[dict] = []

    if not starts:

        return (
            [_record(section.title(), "", lines, source_file, _category_for_section(section))]
            if lines
            else []
        )

    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)

        dated = lines[start]

        # If a company/course name is immediately before a dated role line, retain it as organization.

        organization = ""

        if "|" in dated:
            pipe_parts = [part.strip() for part in dated.split("|")]

            if len(pipe_parts) > 1:
                organization = re.split(r",\s*(?:Supervisor|supervised)\s*:", pipe_parts[1])[
                    0
                ].strip()

        elif (
            start > 0
            and not BULLET_RE.match(lines[start - 1])
            and not DATE_RE.search(lines[start - 1])
        ):
            previous = lines[start - 1]

            if len(previous) < 120 and not re.match(r"^(of|and|to|the)\b", previous, re.I):
                organization = previous
        title = dated

        body_start = start + 1

        if organization:
            body_start = start + 1
        body = lines[body_start:end]

        records.append(
            _record(title, organization, body, source_file, _category_for_section(section))
        )

    return records


def extract_experiences(text: str, source_file: str) -> list[dict]:
    """Deterministic CV extractor used before LLM integration.

    It preserves source text and deliberately leaves uncertain fields blank.

    """

    raw = [_clean(line) for line in text.splitlines() if _clean(line)]

    sections: list[tuple[str, list[str]]] = []

    current = "GENERAL"
    bucket: list[str] = []

    for line in raw:
        match = SECTION_RE.match(line)

        if match:

            if bucket:
                sections.append((current, bucket))

            current = match.group(1).upper()

            bucket = []

        else:
            bucket.append(line)

    if bucket:
        sections.append((current, bucket))

    records: list[dict] = []

    for section, lines in sections:

        if section == "GENERAL":

            continue
        records.extend(_split_section(section, lines, source_file))

    return records or [_record("Uncategorized Experience", "", raw[:16], source_file, "project")]
