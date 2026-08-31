import re

from app.ai.skills import KNOWN_SKILLS

SECTION_RE = re.compile(
    r"^(PERSONAL SKILLS|SKILLS?.*|EDUCATION.*|ENTREPRENEURSHIP.*|"
    r".*WORK(?:ING)? EXPERIENCE|(?:WORK|INTERNSHIP|EMPLOYMENT|PROFESSIONAL|CAREER|RESEARCH|PROJECT|EXPERIENCE).*|"
    r"QUANT INSIGHT EXPERIENCE|RESEARCH EXPERIENCE|LEADERSHIP.*|PROJECTS?|COMPETITION.*|ACTIVITIES|EXTRACURRICULAR.*|VOLUNTEER.*|"
    # 简体中文
    r"工作经历|实习与工作经历|实习经历|职业经历|项目经历|项目经验|研究经历|科研经历|教育经历|教育背景|竞赛.*|获奖.*|志愿.*|课外活动.*|"
    # 繁体中文
    r"工作經歷|實習與工作經歷|實習經歷|職業經歷|專案經歷|專案經驗|專題研究|專題.*|研究經歷|科研經歷|教育經歷|學歷|競賽.*|獲獎.*|志願.*|課外活動.*|社群.*|社團.*)\s*$",
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
    if "education" in section or "教育" in section:
        return "education"
    if "research" in section or "研究" in section or "科研" in section:
        return "research"
    if any(
        word in section
        for word in ("leadership", "entrepreneurship", "activities", "extracurricular", "volunteer",
                     "领导", "社团", "志愿", "活动", "領導", "社團", "志願", "活動")
    ):
        return "leadership"
    if any(
        word in section
        for word in ("work", "internship", "employment", "professional", "career", "quant insight",
                     "work experience", "professional experience", "career experience",
                     "工作", "实习", "职业", "實習", "職業")
    ):
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
        title = ""

        if "|" in dated:
            pipe_parts = [part.strip() for part in dated.split("|")]

            if len(pipe_parts) > 1:
                organization = re.split(r",\s*(?:Supervisor|supervised)\s*:", pipe_parts[1])[
                    0
                ].strip()
            # "Software Engineer | Example Corp | 06/2024 - 08/2024": the
            # leading segment is the role, not a date-only label.
            role = DATE_RE.sub("", pipe_parts[0]).strip(" |,-–\t")
            if len(role) >= 3:
                title = re.sub(r"\s{2,}", " ", role)

        elif (
            start > 0
            and not BULLET_RE.match(lines[start - 1])
            and not DATE_RE.search(lines[start - 1])
        ):
            previous = lines[start - 1]

            if len(previous) < 120 and not re.match(r"^(of|and|to|the)\b", previous, re.I):
                organization = previous
                # Common "Role | Company" line above the dates: use the role
                # as the record title instead of the bare date range, and the
                # company as the organization.
                if "|" in previous:
                    role = DATE_RE.sub("", previous.split("|")[0]).strip(" |,-–\t")
                    if len(role) >= 3:
                        title = re.sub(r"\s{2,}", " ", role)
                    company = previous.split("|", 1)[1].strip()
                    if company:
                        organization = re.split(
                            r",\s*(?:Supervisor|supervised)\s*:", company
                        )[0].strip()
        if not title:
            # A dated heading such as "Analyst Intern, 06/2025 - 08/2025"
            # reads better without the dates.  If the line is ONLY a date the
            # original heading is kept so the record never loses its only
            # label.
            stripped_title = DATE_RE.sub("", dated).strip(" |,-–\t")
            title = (
                re.sub(r"\s{2,}", " ", stripped_title) if len(stripped_title) >= 3 else dated
            )

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

        # A heading never carries dates.  Without this guard the broadened
        # prefixes (RESEARCH/PROJECT/EXPERIENCE...) would swallow content
        # lines such as "Research Assistant, 06/2024 - 08/2024".
        if match and not DATE_RE.search(line):

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
            # A CV whose headings did not match any known section may still
            # hold dated entries (e.g. a Chinese CV or an unusual heading such
            # as "PROFESSIONAL EXPERIENCE" before the regex was broadened).
            # Keep that evidence instead of silently dropping it; fully
            # undated GENERAL content still falls through to the single
            # "Uncategorized Experience" record below.
            if any(DATE_RE.search(line) for line in lines):
                records.extend(
                    _split_section("EXPERIENCE", lines, source_file)
                )
            continue
        records.extend(_split_section(section, lines, source_file))

    return records or [_record("Uncategorized Experience", "", raw[:16], source_file, "project")]
