"""Public-web opportunity discovery grounded in confirmed user evidence."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html import unescape
from urllib.parse import parse_qs, urlparse

import httpx

from app.ai.providers import ProviderError, RateLimitExceeded
from app.config import settings
from app.models.experience import Experience


SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "location": {"type": "string"},
                    "employment_type": {"type": "string"},
                    "why_match": {"type": "string"},
                    "evidence_used": {"type": "array", "items": {"type": "string"}},
                    "gaps_to_address": {"type": "array", "items": {"type": "string"}},
                    "next_step": {"type": "string"},
                    "source_title": {"type": "string"},
                },
                "required": [
                    "company",
                    "title",
                    "why_match",
                    "evidence_used",
                    "gaps_to_address",
                    "next_step",
                    "source_title",
                ],
            },
        }
    },
    "required": ["opportunities"],
}


def _compact_evidence(experiences: list[Experience]) -> list[dict]:
    return [
        {
            "id": item.id,
            "title": item.title[:200],
            "organization": item.organization[:200],
            "skills": [str(skill)[:80] for skill in (item.skills or [])[:20]],
            # Keep the outgoing content identical to the preview shown in the
            # browser. The user should never have to guess which portion of a
            # confirmed experience is being used for public-web research.
            "description": item.description[:180],
        }
        for item in experiences
        if item.confirmed
    ]


def _matching_source(source_title: str, sources: list[dict[str, str]]) -> dict[str, str] | None:
    """Return only URLs supplied by the configured web-search provider.

    The model is never allowed to invent a link. It must name a returned source
    title, and we attach the corresponding metadata URL ourselves.
    """
    wanted = " ".join(source_title.casefold().split())
    if not wanted:
        return None

    # Search providers often label a source with its bare domain
    # (``janestreet.com``), whereas the model naturally refers to it as
    # ``Jane Street careers``.  Literal matching made that safe check too
    # strict: the search succeeded, but every otherwise grounded candidate was
    # discarded.  Compare a conservative alphanumeric identity as a second
    # pass while still returning *only* the URL from grounding metadata.
    def identity(value: str) -> str:
        value = value.casefold().strip()
        value = re.sub(r"^https?://", "", value)
        value = re.sub(r"^www\.", "", value)
        value = re.sub(r"\.(com|org|net|edu|gov|io|ai|co|hk|uk|us|cn)\b", "", value)
        return re.sub(r"[^a-z0-9]+", "", value)

    wanted_identity = identity(source_title)
    for source in sources:
        title = " ".join(str(source.get("title", "")).casefold().split())
        if wanted == title or wanted in title or title in wanted:
            return source
        title_identity = identity(title)
        if (
            wanted_identity
            and title_identity
            and (
                wanted_identity == title_identity
                or wanted_identity in title_identity
                or title_identity in wanted_identity
            )
        ):
            return source
    return None


_OFFICIAL_ATS_HOSTS = {
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
}

_BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
_BOCHA_WEB_SEARCH_URL = "https://api.bochaai.com/v1/web-search"

# Lever publishes public, employer-owned JSON feeds.  These feeds do not need a
# search key and the returned hostedUrl stays on the employer's own Lever page.
# Keep this deliberately small and reviewed rather than pretending that an
# unauthenticated crawler covers the whole market.
_LEVER_PUBLIC_FEEDS = {
    "ekimetrics": "Ekimetrics",
    "neon": "Neon",
}

# Greenhouse's public Job Board API is employer-owned, needs no API key and
# exposes the current board rather than a search-engine cache.  Together these
# reviewed boards provide a much broader student-role pool (technology, AI,
# data and quantitative finance) while every result still links back to the
# employer's own application page.
_GREENHOUSE_PUBLIC_BOARDS = {
    "stripe": "Stripe",
    "datadog": "Datadog",
    "cloudflare": "Cloudflare",
    "scaleai": "Scale AI",
    "point72": "Point72",
    "jumptrading": "Jump Trading",
    "verkada": "Verkada",
    "figma": "Figma",
    "databricks": "Databricks",
    "coinbase": "Coinbase",
    "ripple": "Ripple",
    "block": "Block",
}

_STUDENT_ROLE_PATTERN = re.compile(
    r"\b(?:intern(?:ship)?|graduate|new[ -]?grad|campus|co-op)\b", re.I
)


def _official_ats_url(value: str) -> str | None:
    """Accept only direct, public pages on well-known employer ATS hosts.

    DuckDuckGo result links are redirected through ``uddg``; unwrap only that
    documented parameter and never follow arbitrary redirects ourselves.
    """
    parsed = urlparse(value)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        value = parse_qs(parsed.query).get("uddg", [""])[0]
        parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or host not in _OFFICIAL_ATS_HOSTS:
        return None
    path = parsed.path.rstrip("/")
    if host.endswith("greenhouse.io") and "/jobs/" not in path:
        return None
    if host == "jobs.lever.co" and len([part for part in path.split("/") if part]) < 2:
        return None
    if host == "jobs.ashbyhq.com" and len([part for part in path.split("/") if part]) < 2:
        return None
    return parsed._replace(fragment="").geturl()


def _search_title(value: str) -> str:
    value = unescape(unescape(value))
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()[:200]


def _plain_html(value: str, *, limit: int = 12000) -> str:
    value = unescape(unescape(value))
    value = re.sub(r"(?is)<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _safe_greenhouse_destination(value: str) -> str | None:
    """Validate a destination supplied by the official Greenhouse API.

    Employers often use a careers-domain wrapper instead of a greenhouse.io
    URL.  It is safe to retain that API-supplied HTTPS destination, but never a
    local address, credential-bearing URL or non-HTTP scheme.
    """
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or host in {"localhost", "127.0.0.1", "::1"}
    ):
        return None
    return parsed._replace(fragment="").geturl()


def _company_from_ats_url(url: str) -> str:
    parsed = urlparse(url)
    bits = [part for part in parsed.path.split("/") if part]
    host = (parsed.hostname or "").casefold()
    if bits and host in _OFFICIAL_ATS_HOSTS:
        return bits[0].replace("-", " ").title()[:200]
    return "Official employer"


def _localized_ats_copy(language: str, skill_preview: str) -> tuple[str, str]:
    if language == "zh-TW":
        return (
            f"此職缺來自僱主公開的官方招聘系統；搜尋使用了你核對過的方向與技能{('：' + skill_preview) if skill_preview else ''}。",
            "開啟官方職缺頁核對要求，再決定是否匯入分析。",
        )
    if language == "zh-CN":
        return (
            f"该职位来自雇主公开的官方招聘系统；搜索使用了你确认过的方向与技能{('：' + skill_preview) if skill_preview else ''}。",
            "打开官方职位页核对要求，再决定是否导入分析。",
        )
    return (
        f"This opening is on an employer's official applicant-tracking page and was found using your approved direction and skills{(': ' + skill_preview) if skill_preview else ''}.",
        "Review the official posting, then import it for a full evidence match.",
    )


def _unique_strings(values: list[str], *, limit: int = 6) -> list[str]:
    """Return concise, stable display values without repeated skills."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = " ".join(str(raw).split()).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
        if len(result) >= limit:
            break
    return result


def _localized_role_reason(
    language: str,
    *,
    company: str,
    title: str,
    career_goal: str,
    evidence: list[dict],
) -> str:
    """Explain the specific result, not the generic fact that an ATS exists.

    The earlier implementation put the same ATS disclosure in ``why_match``
    for every result.  That made distinct openings look like model duplicates.
    This stays deliberately conservative: it only names the user's selected
    direction and confirmed evidence, and never claims a requirement was met.
    """
    evidence_names = _unique_strings([str(item.get("title", "")) for item in evidence], limit=2)
    skills = _unique_strings(
        [str(skill) for item in evidence for skill in item.get("skills", [])], limit=4
    )
    goal = " ".join(career_goal.split())[:120]
    evidence_text = (
        "、".join(evidence_names) if language.startswith("zh") else ", ".join(evidence_names)
    )
    skills_text = "、".join(skills) if language.startswith("zh") else ", ".join(skills)
    if language == "zh-TW":
        direction = f"你設定的「{goal}」方向" if goal else "你已確認的探索方向"
        proof = evidence_text or skills_text or "已確認經歷"
        return f"「{company} · {title}」與{direction}有交集；可先以{proof}作為可核對的申請證據。"
    if language == "zh-CN":
        direction = f"你设定的“{goal}”方向" if goal else "你已确认的探索方向"
        proof = evidence_text or skills_text or "已确认经历"
        return f"“{company} · {title}”与{direction}有交集；可先以{proof}作为可核对的申请证据。"
    direction = (
        f"your stated direction, “{goal}”" if goal else "your confirmed exploration direction"
    )
    proof = evidence_text or skills_text or "your confirmed evidence"
    return f"“{company} · {title}” overlaps with {direction}; start by reviewing how {proof} can support an honest application."


def _normalise_location(value: str) -> str:
    value = value.casefold().strip()
    aliases = {
        "hong kong": "hong kong",
        "hkg": "hong kong",
        "香港": "hong kong",
        "new york": "new york",
        "nyc": "new york",
        "new york city": "new york",
    }
    return aliases.get(value, value)


def _location_rank(posting_location: str, requested_location: str) -> int:
    """Keep job type as the main signal, then rank exact locations above all.

    A role with no published location is kept as a lower-confidence result;
    a known mismatched city must never leap ahead of an exact requested city.
    """
    wanted = _normalise_location(requested_location)
    actual = _normalise_location(posting_location)
    if not wanted:
        return 1
    if wanted and (wanted in actual or actual in wanted):
        return 2
    if not actual:
        return 1
    return 0


def _honest_gaps(evidence: list[dict], role_text: str, language: str = "en") -> list[str]:
    """Infer only absence from confirmed evidence; never claim a missing skill.

    Direct ATS feeds frequently do not expose a full job description. These
    are conservative preparation prompts, not assertions about requirements.
    """
    known = " ".join(
        " ".join(
            [
                str(item.get("title", "")),
                str(item.get("description", "")),
                *map(str, item.get("skills", [])),
            ]
        )
        for item in evidence
    ).casefold()
    target = role_text.casefold()
    gaps: list[str] = []
    checks = [
        (
            ("quant", "trader", "trading", "research"),
            ("probability", "statistics", "statistical"),
            "probability",
        ),
        (
            ("quant", "trader", "trading"),
            ("market microstructure", "trading", "finance"),
            "trading_domain",
        ),
        (
            ("engineer", "software", "developer", "api"),
            ("api", "testing", "test", "system"),
            "engineering",
        ),
        (
            ("data", "machine learning", "ml", "ai"),
            ("sql", "data pipeline", "model evaluation"),
            "data_model",
        ),
        (
            ("strategy", "consult", "client"),
            ("stakeholder", "consult", "business", "client"),
            "stakeholder",
        ),
    ]
    labels = {
        "en": {
            "probability": "Probability and statistical reasoning",
            "trading_domain": "Market or trading-domain evidence",
            "engineering": "Production engineering or testing evidence",
            "data_model": "Role-specific data or model-evaluation evidence",
            "stakeholder": "Stakeholder or business-problem framing evidence",
            "review": "No unsupported capability gap is visible in the public summary; verify role-specific requirements on the official page.",
        },
        "zh-CN": {
            "probability": "概率与统计推理的可解释案例",
            "trading_domain": "市场或量化交易领域的真实证据",
            "engineering": "生产工程、API 或测试的真实证据",
            "data_model": "与该岗位相关的数据或模型评估证据",
            "stakeholder": "业务问题拆解或利益相关者协作的真实案例",
            "review": "公开摘要未显示可断言的技能缺口；请在官方职位页核对岗位专属要求。",
        },
        "zh-TW": {
            "probability": "機率與統計推理的可解釋案例",
            "trading_domain": "市場或量化交易領域的真實證據",
            "engineering": "生產工程、API 或測試的真實證據",
            "data_model": "與該職位相關的資料或模型評估證據",
            "stakeholder": "商業問題拆解或利害關係人協作的真實案例",
            "review": "公開摘要未顯示可斷言的技能缺口；請在官方職缺頁核對職位專屬要求。",
        },
    }.get(language, {})
    for role_terms, evidence_terms, label_key in checks:
        if any(term in target for term in role_terms) and not any(
            term in known for term in evidence_terms
        ):
            gaps.append(labels.get(label_key, label_key))
    # An empty card reads as an assertion that nothing needs work.  This is a
    # review prompt, not a fabricated gap, and makes the uncertainty explicit.
    return gaps[:3] or [
        labels.get("review", "Verify role-specific requirements on the official page.")
    ]


def _extract_location_from_text(value: str) -> str:
    """Extract only a known location; never label an unknown role as requested."""
    text = value.casefold()
    for marker, canonical in (
        ("hong kong", "Hong Kong"),
        ("hkg", "Hong Kong"),
        ("香港", "Hong Kong"),
        ("shanghai", "Shanghai"),
        ("new york", "New York"),
        ("nyc", "New York"),
        ("london", "London"),
        ("singapore", "Singapore"),
    ):
        if marker in text:
            return canonical
    return ""


def _is_stale_internship(title: str, role_text: str = "") -> bool:
    """Do not surface internships whose advertised start period has passed.

    Public ATS feeds are inconsistent about a close date.  We only reject an
    explicit internship/program period (for example ``July 2026`` or
    ``2026-07``), not an arbitrary old page timestamp.
    """
    text = f"{title} {role_text}".casefold()
    today = date.today()
    current_month = (today.year, today.month)
    for year, month in re.findall(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b", text):
        if (int(year), int(month)) < current_month and re.search(
            r"intern|program|start|join", text
        ):
            return True
    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    for month_name, month in months.items():
        found = re.search(rf"\b{month_name}\s+(20\d{{2}})\b", text)
        if (
            found
            and (int(found.group(1)), month) < current_month
            and re.search(r"intern|program|start|join", text)
        ):
            return True
    if "summer 2026" in text and today >= date(2026, 8, 1):
        return True
    return False


def _dynamic_next_step(
    language: str, gaps: list[str], evidence_names: list[str], title: str
) -> str:
    subject = (
        gaps[0] if gaps else (evidence_names[0] if evidence_names else "your confirmed evidence")
    )
    if language == "zh-TW":
        return f"先核對「{title}」的官方要求；再用{subject}準備一個可解釋的例子。"
    if language == "zh-CN":
        return f"先核对“{title}”的官方要求；再围绕{subject}准备一个可解释的例子。"
    return f"Review the official requirements for “{title}”, then prepare one explainable example around {subject}."


def _rank_opportunities(rows: list[dict], *, career_goal: str, location: str) -> list[dict]:
    goal_tokens = _career_search_terms(career_goal, [])

    def rank(row: dict) -> tuple[int, int, int]:
        title = str(row.get("title", "")).casefold()
        # The user's requested kind of work is the primary signal, their
        # selected location is second, and student-role suitability is third.
        # This is intentionally a preference rather than a hard location gate.
        role_rank = 2 if re.search(r"\b(intern|internship|graduate)\b", title) else 1
        overlap = sum(token in title for token in goal_tokens)
        return overlap, _location_rank(str(row.get("location", "")), location), role_rank

    # Location is a ranking preference, not a hidden hard filter. If a city
    # has no currently open role, verified alternatives are still useful and
    # must remain visible rather than making the search appear broken.
    return sorted(rows, key=rank, reverse=True)


def _lever_public_feed_search(
    evidence: list[dict], *, career_goal: str, location: str, language: str, limit: int
) -> dict:
    """Search reviewed official Lever feeds without an AI or search-engine key."""
    skills = [skill.casefold() for item in evidence for skill in item.get("skills", [])]
    tokens = {
        token
        for token in re.findall(r"[a-z0-9+#.-]{3,}", f"{career_goal} {' '.join(skills)}".casefold())
        if token not in {"intern", "internship", "experience", "research"}
    }
    location_term = location.casefold().strip()
    candidates: list[tuple[int, int, dict]] = []
    for slug, company in _LEVER_PUBLIC_FEEDS.items():
        try:
            response = httpx.get(
                f"https://api.lever.co/v0/postings/{slug}",
                params={"mode": "json"},
                headers={"User-Agent": "ApplyEaseOpportunityRadar/1.0"},
                timeout=8.0,
                trust_env=False,
            )
            response.raise_for_status()
            postings = response.json()
        except (httpx.HTTPError, ValueError, AttributeError):
            continue
        if not isinstance(postings, list):
            continue
        for posting in postings:
            if not isinstance(posting, dict):
                continue
            title = str(posting.get("text", "")).strip()[:200]
            hosted_url = _official_ats_url(str(posting.get("hostedUrl", "")))
            categories = (
                posting.get("categories") if isinstance(posting.get("categories"), dict) else {}
            )
            description = str(posting.get("descriptionPlain", ""))[:12000]
            posting_location = str(categories.get("location", "")).strip()[
                :200
            ] or _extract_location_from_text(title)
            role_text = " ".join([title, description, str(categories.get("team", ""))])
            haystack = role_text.casefold()
            if not title or not hosted_url or "intern" not in title.casefold():
                continue
            if _is_stale_internship(title, role_text):
                continue
            score = sum(token in haystack for token in tokens)
            location_score = _location_rank(posting_location, location_term)
            # Returned postings remain real even where a student has not named
            # a narrowly matching skill; location and internship status retain
            # a useful, transparent baseline for exploration.
            candidates.append(
                (
                    score,
                    location_score,
                    {
                        "company": company,
                        "title": title,
                        "location": posting_location,
                        "employment_type": str(categories.get("commitment", "Internship"))[:100],
                        "source_title": f"{title} | {company}",
                        "source_url": hosted_url,
                        "_role_text": role_text,
                    },
                )
            )
    # A relevant internship remains the first gate; within that set, exact
    # requested locations always come before other cities.
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    evidence_names = [str(item["title"]) for item in evidence[:3] if item.get("title")]
    results = [
        {
            **posting,
            "why_match": _localized_role_reason(
                language,
                company=posting["company"],
                title=posting["title"],
                career_goal=career_goal,
                evidence=evidence,
            ),
            "evidence_used": evidence_names,
            "gaps_to_address": _honest_gaps(
                evidence, f"{posting['_role_text']} {career_goal}", language
            ),
            "next_step": _dynamic_next_step(
                language,
                _honest_gaps(evidence, f"{posting['_role_text']} {career_goal}", language),
                evidence_names,
                posting["title"],
            ),
            "source_search_mode": "official_ats",
        }
        for _, _, posting in candidates[:limit]
    ]
    for result in results:
        result.pop("_role_text", None)
    return {
        "opportunities": results,
        "sources": [{"title": item["source_title"], "url": item["source_url"]} for item in results],
        "used_fallback": True,
        "unavailable_reason": "ats_fallback",
    }


def _career_search_terms(career_goal: str, evidence: list[dict]) -> set[str]:
    """Build useful English terms even when the student's goal is Chinese."""
    raw = f"{career_goal} " + " ".join(
        str(skill) for item in evidence for skill in item.get("skills", [])
    )
    terms = {
        token
        for token in re.findall(r"[a-z0-9+#.-]{2,}", raw.casefold())
        if token
        not in {
            "and",
            "the",
            "with",
            "intern",
            "internship",
            "experience",
            "role",
            "job",
        }
    }
    lowered = career_goal.casefold()
    expansions = (
        (("量化", "quant"), {"quant", "quantitative", "trading", "research"}),
        (("人工智能", "ai", "machine learning", "机器学习", "機器學習"), {"ai", "machine", "learning", "research", "engineer"}),
        (("数据", "資料", "data"), {"data", "analytics", "science"}),
        (("软件", "軟體", "software", "编程", "編程"), {"software", "engineer", "developer"}),
        (("金融", "finance"), {"finance", "trading", "investment", "quantitative"}),
        (("产品", "產品", "product"), {"product"}),
    )
    for markers, additions in expansions:
        if any(marker in lowered for marker in markers):
            terms.update(additions)
    return terms


def _greenhouse_public_board_search(
    evidence: list[dict], *, career_goal: str, location: str, language: str, limit: int
) -> dict:
    """Search a reviewed set of high-volume official Greenhouse boards.

    Board indexes are fetched concurrently and contain only lightweight job
    metadata.  We then fetch full descriptions for a short ranked shortlist,
    so the radar is broad without becoming slow or downloading thousands of
    descriptions on every click.
    """

    def fetch_board(item: tuple[str, str]) -> tuple[str, str, list[dict]]:
        token, company = item
        try:
            response = httpx.get(
                f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                headers={"User-Agent": "ApplyEaseOpportunityRadar/1.0"},
                timeout=10.0,
                trust_env=False,
            )
            response.raise_for_status()
            payload = response.json()
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
            return token, company, jobs if isinstance(jobs, list) else []
        except (httpx.HTTPError, ValueError, AttributeError, TypeError):
            return token, company, []

    board_rows: list[tuple[str, str, list[dict]]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(_GREENHOUSE_PUBLIC_BOARDS))) as pool:
        futures = [pool.submit(fetch_board, item) for item in _GREENHOUSE_PUBLIC_BOARDS.items()]
        for future in as_completed(futures):
            board_rows.append(future.result())

    terms = _career_search_terms(career_goal, evidence)
    candidates: list[tuple[int, int, dict]] = []
    for token, default_company, jobs in board_rows:
        for posting in jobs:
            if not isinstance(posting, dict):
                continue
            title = " ".join(str(posting.get("title", "")).split())[:200]
            if not title or not _STUDENT_ROLE_PATTERN.search(title):
                continue
            destination = _safe_greenhouse_destination(str(posting.get("absolute_url", "")))
            if not destination or _is_stale_internship(title):
                continue
            location_payload = posting.get("location")
            posting_location = (
                str(location_payload.get("name", "")).strip()[:200]
                if isinstance(location_payload, dict)
                else ""
            )
            title_text = title.casefold()
            relevance = sum(2 if term in title_text else 0 for term in terms)
            # Do not turn a large feed into noise. A narrow career goal must
            # overlap the title; an empty goal may still explore student roles.
            if terms and relevance == 0:
                continue
            company = str(posting.get("company_name", "")).strip()[:200] or default_company
            candidates.append(
                (
                    relevance,
                    _location_rank(posting_location, location),
                    {
                        "board_token": token,
                        "job_id": posting.get("id"),
                        "company": company,
                        "title": title,
                        "location": posting_location,
                        "employment_type": (
                            "Internship"
                            if re.search(r"\bintern(?:ship)?\b", title, re.I)
                            else "Graduate / campus role"
                        ),
                        "source_title": f"{title} | {company}",
                        "source_url": destination,
                    },
                )
            )

    candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
    shortlist = [row[2] for row in candidates[: max(limit * 3, 12)]]

    def fetch_detail(posting: dict) -> tuple[dict, str]:
        try:
            response = httpx.get(
                "https://boards-api.greenhouse.io/v1/boards/"
                f"{posting['board_token']}/jobs/{posting['job_id']}",
                headers={"User-Agent": "ApplyEaseOpportunityRadar/1.0"},
                timeout=10.0,
                trust_env=False,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload.get("content", "") if isinstance(payload, dict) else ""
            return posting, _plain_html(str(content))
        except (httpx.HTTPError, ValueError, AttributeError, TypeError, KeyError):
            return posting, ""

    detailed: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(shortlist)))) as pool:
        futures = [pool.submit(fetch_detail, posting) for posting in shortlist]
        for future in as_completed(futures):
            posting, description = future.result()
            role_text = f"{posting['title']} {description}"
            if _is_stale_internship(posting["title"], role_text):
                continue
            evidence_names = [str(item["title"]) for item in evidence[:3] if item.get("title")]
            gaps = _honest_gaps(evidence, f"{role_text} {career_goal}", language)
            detailed.append(
                {
                    "company": posting["company"],
                    "title": posting["title"],
                    "location": posting["location"],
                    "employment_type": posting["employment_type"],
                    "why_match": _localized_role_reason(
                        language,
                        company=posting["company"],
                        title=posting["title"],
                        career_goal=career_goal,
                        evidence=evidence,
                    ),
                    "evidence_used": evidence_names,
                    "gaps_to_address": gaps,
                    "next_step": _dynamic_next_step(
                        language, gaps, evidence_names, posting["title"]
                    ),
                    "source_title": posting["source_title"],
                    "source_url": posting["source_url"],
                    "source_search_mode": "official_ats",
                }
            )

    results = _dedupe_and_rank(
        detailed, career_goal=career_goal, location=location, limit=limit
    )
    return {
        "opportunities": results,
        "sources": [{"title": row["source_title"], "url": row["source_url"]} for row in results],
        "used_fallback": True,
        "unavailable_reason": "ats_fallback",
    }


def _direct_ats_search(
    evidence: list[dict], *, career_goal: str, location: str, language: str, limit: int
) -> dict:
    """Keyless search fallback over direct employer ATS pages.

    This deliberately does not ask another model to invent positions. It sends
    a compact user-approved direction plus a few visible confirmed skills to a
    public search engine, and returns only direct Greenhouse/Lever/Ashby pages.
    """
    greenhouse_result = _greenhouse_public_board_search(
        evidence,
        career_goal=career_goal,
        location=location,
        language=language,
        limit=max(limit, 8),
    )
    lever_result = _lever_public_feed_search(
        evidence, career_goal=career_goal, location=location, language=language, limit=limit
    )
    verified = _dedupe_and_rank(
        [*greenhouse_result["opportunities"], *lever_result["opportunities"]],
        career_goal=career_goal,
        location=location,
        limit=limit,
    )
    if verified:
        verified_urls = {str(row.get("source_url", "")) for row in verified}
        return {
            "opportunities": verified,
            "sources": _dedupe_sources(
                [
                    source
                    for source in [
                        *greenhouse_result["sources"],
                        *lever_result["sources"],
                    ]
                    if str(source.get("url", "")) in verified_urls
                ]
            ),
            "used_fallback": True,
            "unavailable_reason": "ats_fallback",
        }

    skills = " ".join(skill for item in evidence for skill in item.get("skills", [])).strip()
    query_terms = " ".join(
        value for value in [career_goal, skills[:180], location, "internship"] if value
    )
    query = (
        f"{query_terms} (site:boards.greenhouse.io OR site:jobs.lever.co OR "
        "site:jobs.ashbyhq.com)"
    )
    try:
        response = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "ApplyEaseOpportunityRadar/1.0"},
            timeout=8.0,
            follow_redirects=True,
            trust_env=False,
        )
        # DuckDuckGo returns HTTP 202 when its anti-bot challenge is served.
        # Treat that as a provider outage, never as proof that no vacancies
        # exist.  The UI can then explain the real limitation rather than
        # presenting an indistinguishable empty search.
        if getattr(response, "status_code", 200) == 202:
            return {
                "opportunities": [],
                "sources": [],
                "used_fallback": True,
                "unavailable_reason": "provider_unavailable",
            }
        response.raise_for_status()
    except httpx.HTTPError:
        return {
            "opportunities": [],
            "sources": [],
            "used_fallback": True,
            "unavailable_reason": "provider_unavailable",
        }

    # Attribute order is not stable across DuckDuckGo's HTML variants. Parse
    # every anchor, then select result anchors by class instead of assuming
    # that ``class`` appears before ``href``.
    pairs: list[tuple[str, str]] = []
    for attributes, body in re.findall(r"(?is)<a\b([^>]*)>(.*?)</a>", response.text):
        if "result__a" not in attributes:
            continue
        href_match = re.search(r"""(?is)\bhref\s*=\s*["']([^"']+)["']""", attributes)
        if href_match:
            pairs.append((href_match.group(1), body))
    sources: list[dict[str, str]] = []
    results: list[dict] = []
    seen: set[str] = set()
    evidence_names = [str(item["title"]) for item in evidence[:3] if item.get("title")]
    for href, raw_title in pairs:
        url = _official_ats_url(unescape(href))
        title = _search_title(raw_title)
        if not url or not title or url in seen:
            continue
        if not re.search(
            r"\b(intern|internship|graduate|research|engineer|analyst|trader|developer)\b",
            title,
            re.I,
        ):
            continue
        inferred_location = _extract_location_from_text(title)
        if _is_stale_internship(title):
            continue
        seen.add(url)
        company = _company_from_ats_url(url)
        source = {"title": title, "url": url}
        sources.append(source)
        gaps = _honest_gaps(evidence, f"{title} {career_goal}", language)
        results.append(
            {
                "company": company,
                "title": title,
                "location": inferred_location,
                "employment_type": "Internship",
                "why_match": _localized_role_reason(
                    language,
                    company=company,
                    title=title,
                    career_goal=career_goal,
                    evidence=evidence,
                ),
                "evidence_used": evidence_names,
                "gaps_to_address": gaps,
                "next_step": _dynamic_next_step(language, gaps, evidence_names, title),
                "source_title": title,
                "source_url": url,
                "source_search_mode": "official_ats",
            }
        )
        if len(results) >= limit:
            break
    results = _rank_opportunities(results, career_goal=career_goal, location=location)[:limit]
    return {
        "opportunities": results,
        "sources": sources[:8],
        "used_fallback": True,
        "unavailable_reason": "ats_fallback",
    }


def _brave_ats_search(
    evidence: list[dict], *, career_goal: str, location: str, language: str, limit: int
) -> dict:
    """Search current official ATS pages using Brave's independent web index.

    The request contains only the evidence summary the user explicitly chose
    for this search.  We use separate Greenhouse, Lever, and Ashby queries so
    one employer's ATS does not dominate the result set, and accept only a
    direct official ATS URL from the response.  This keeps web search broad
    while preserving the same review/import safety boundary as the keyless
    official-board search.
    """
    token = settings.brave_search_api_key.strip()
    if not token:
        raise ProviderError("Brave Search API key is not configured")

    terms = sorted(_career_search_terms(career_goal, evidence))[:8]
    query_terms = " ".join(terms) or "student early career"
    location_terms = location.strip()[:120]
    query_tail = " ".join(value for value in [query_terms, location_terms, "internship"] if value)
    hosts = ("boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com")
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": token,
        "User-Agent": "ApplyEaseOpportunityRadar/1.0",
    }
    raw_results: list[dict] = []
    for host in hosts[: settings.brave_search_max_requests]:
        try:
            response = httpx.get(
                _BRAVE_WEB_SEARCH_URL,
                params={"q": f"site:{host} {query_tail}", "count": 10, "search_lang": "en"},
                headers=headers,
                timeout=settings.brave_search_timeout_seconds,
                trust_env=False,
            )
            if response.status_code == 429:
                raise RateLimitExceeded("Brave Search API quota is temporarily exhausted")
            response.raise_for_status()
            payload = response.json()
        except RateLimitExceeded:
            raise
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as exc:
            raise ProviderError("Brave web research failed") from exc
        web = payload.get("web", {}) if isinstance(payload, dict) else {}
        rows = web.get("results", []) if isinstance(web, dict) else []
        raw_results.extend(row for row in rows if isinstance(row, dict))

    evidence_names = [str(item["title"]) for item in evidence[:3] if item.get("title")]
    candidates: list[dict] = []
    seen_urls: set[str] = set()
    for row in raw_results:
        url = _official_ats_url(str(row.get("url", "")))
        title = _search_title(str(row.get("title", "")))
        description = _search_title(str(row.get("description", "")))
        role_text = f"{title} {description}"
        if not url or not title or url in seen_urls:
            continue
        if not _STUDENT_ROLE_PATTERN.search(role_text) or _is_stale_internship(title, role_text):
            continue
        seen_urls.add(url)
        company = _company_from_ats_url(url)
        posting_location = _extract_location_from_text(role_text)
        gaps = _honest_gaps(evidence, f"{role_text} {career_goal}", language)
        candidates.append(
            {
                "company": company,
                "title": title[:200],
                "location": posting_location,
                "employment_type": "Internship",
                "why_match": _localized_role_reason(
                    language,
                    company=company,
                    title=title,
                    career_goal=career_goal,
                    evidence=evidence,
                ),
                "evidence_used": evidence_names,
                "gaps_to_address": gaps,
                "next_step": _dynamic_next_step(language, gaps, evidence_names, title),
                "source_title": title[:240],
                "source_url": url,
                "source_search_mode": "ai",
            }
        )
    results = _dedupe_and_rank(candidates, career_goal=career_goal, location=location, limit=limit)
    return {
        "opportunities": results,
        "sources": [{"title": row["source_title"], "url": row["source_url"]} for row in results],
        "used_fallback": False,
        "unavailable_reason": "",
    }


def _bocha_ats_search(
    evidence: list[dict], *, career_goal: str, location: str, language: str, limit: int
) -> dict:
    """Search official ATS pages with Bocha, the preferred domestic provider."""
    token = settings.bocha_search_api_key.strip()
    if not token:
        raise ProviderError("Bocha Search API key is not configured")

    terms = sorted(_career_search_terms(career_goal, evidence))[:8]
    query_terms = " ".join(terms) or "student early career"
    query_tail = " ".join(
        value for value in [query_terms, location.strip()[:120], "internship"] if value
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "ApplyEaseOpportunityRadar/1.0",
    }
    raw_results: list[dict] = []
    for host in ("boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com")[: settings.bocha_search_max_requests]:
        try:
            response = httpx.post(
                _BOCHA_WEB_SEARCH_URL,
                json={
                    "query": query_tail,
                    "count": 10,
                    "summary": False,
                    # Bocha's domain filter is more reliable than asking the
                    # public-index query parser to interpret a search-engine
                    # ``site:`` operator.  We still validate every returned
                    # URL ourselves below.
                    "include": host,
                },
                headers=headers,
                timeout=settings.bocha_search_timeout_seconds,
                trust_env=False,
            )
            if response.status_code == 429:
                raise RateLimitExceeded("Bocha Search API quota is temporarily exhausted")
            response.raise_for_status()
            payload = response.json()
        except RateLimitExceeded:
            raise
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as exc:
            raise ProviderError("Bocha web research failed") from exc
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        pages = data.get("webPages", {}) if isinstance(data, dict) else {}
        rows = pages.get("value", []) if isinstance(pages, dict) else []
        raw_results.extend(row for row in rows if isinstance(row, dict))

    evidence_names = [str(item["title"]) for item in evidence[:3] if item.get("title")]
    candidates: list[dict] = []
    seen_urls: set[str] = set()
    for row in raw_results:
        url = _official_ats_url(str(row.get("url", "")))
        title = _search_title(str(row.get("name", "")))
        description = _search_title(str(row.get("snippet", "")))
        role_text = f"{title} {description}"
        if not url or not title or url in seen_urls:
            continue
        if not _STUDENT_ROLE_PATTERN.search(role_text) or _is_stale_internship(title, role_text):
            continue
        seen_urls.add(url)
        company = _company_from_ats_url(url)
        posting_location = _extract_location_from_text(role_text)
        gaps = _honest_gaps(evidence, f"{role_text} {career_goal}", language)
        candidates.append(
            {
                "company": company,
                "title": title[:200],
                "location": posting_location,
                "employment_type": "Internship",
                "why_match": _localized_role_reason(
                    language,
                    company=company,
                    title=title,
                    career_goal=career_goal,
                    evidence=evidence,
                ),
                "evidence_used": evidence_names,
                "gaps_to_address": gaps,
                "next_step": _dynamic_next_step(language, gaps, evidence_names, title),
                "source_title": title[:240],
                "source_url": url,
                "source_search_mode": "ai",
            }
        )
    results = _dedupe_and_rank(candidates, career_goal=career_goal, location=location, limit=limit)
    return {
        "opportunities": results,
        "sources": [{"title": row["source_title"], "url": row["source_url"]} for row in results],
        "used_fallback": False,
        "unavailable_reason": "",
    }


def discover_opportunities(
    experiences: list[Experience],
    *,
    career_goal: str,
    location: str,
    work_preference: str,
    timing: str,
    language: str,
    limit: int,
    search_modes: list[str],
) -> dict:
    evidence = _compact_evidence(experiences)
    results: list[dict] = []
    sources: list[dict] = []
    outcomes: list[dict[str, str | int]] = []
    used_fallback = False
    unavailable_reason = ""
    if "official_ats" in search_modes:
        ats = _direct_ats_search(
            evidence, career_goal=career_goal, location=location, language=language, limit=limit
        )
        results.extend(ats["opportunities"])
        sources.extend(ats["sources"])
        status = "success" if ats["opportunities"] else "failed"
        outcomes.append(
            {"mode": "official_ats", "status": status, "count": len(ats["opportunities"])}
        )
        used_fallback = bool(ats["used_fallback"])
        if not ats["opportunities"]:
            unavailable_reason = str(ats["unavailable_reason"])

    if "ai" not in search_modes:
        deduped = _dedupe_and_rank(results, career_goal=career_goal, location=location, limit=limit)
        return {
            "opportunities": deduped,
            "sources": _dedupe_sources(sources),
            "used_fallback": used_fallback,
            "unavailable_reason": unavailable_reason,
            "strategy_outcomes": outcomes,
        }

    try:
        search_kwargs = {
            "career_goal": career_goal,
            "location": location,
            "language": language,
            "limit": limit,
        }
        if settings.bocha_search_api_key.strip():
            try:
                web_search = _bocha_ats_search(evidence, **search_kwargs)
            except (ProviderError, RateLimitExceeded):
                if not settings.brave_search_api_key.strip():
                    raise
                web_search = _brave_ats_search(evidence, **search_kwargs)
        else:
            web_search = _brave_ats_search(evidence, **search_kwargs)
        # A successful public index request can still have no fresh job-page
        # hit for a narrow role/location combination.  In that case, broaden
        # the same consented search with the reviewed official ATS feeds
        # rather than presenting an indistinguishable empty result.
        if not web_search["opportunities"]:
            ats_fallback = _direct_ats_search(evidence, **search_kwargs)
            if ats_fallback["opportunities"]:
                web_search = {
                    "opportunities": ats_fallback["opportunities"],
                    "sources": ats_fallback["sources"],
                    "used_fallback": True,
                    "unavailable_reason": "ats_fallback",
                }
        ai_results = web_search["opportunities"]
        results.extend(ai_results)
        sources.extend(web_search["sources"])
        used_fallback = used_fallback or bool(web_search["used_fallback"])
        outcomes.append(
            {
                "mode": "ai",
                "status": "success" if ai_results else "failed",
                "count": len(ai_results),
            }
        )
        return {
            "opportunities": _dedupe_and_rank(
                results, career_goal=career_goal, location=location, limit=limit
            ),
            "sources": _dedupe_sources(sources),
            "used_fallback": used_fallback,
            "unavailable_reason": unavailable_reason,
            "strategy_outcomes": outcomes,
        }
    except RateLimitExceeded:
        outcomes.append({"mode": "ai", "status": "quota_exhausted", "count": 0})
        unavailable_reason = "quota_exhausted"
    except ProviderError:
        outcomes.append({"mode": "ai", "status": "failed", "count": 0})
        unavailable_reason = "provider_unavailable"
    return {
        "opportunities": _dedupe_and_rank(
            results, career_goal=career_goal, location=location, limit=limit
        ),
        "sources": _dedupe_sources(sources),
        "used_fallback": used_fallback,
        "unavailable_reason": unavailable_reason,
        "strategy_outcomes": outcomes,
    }


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    seen: set[str] = set()
    return [
        item
        for item in sources
        if item.get("url") and not (str(item["url"]) in seen or seen.add(str(item["url"])))
    ][:8]


def _dedupe_and_rank(
    rows: list[dict], *, career_goal: str, location: str, limit: int
) -> list[dict]:
    unique_by_role: dict[tuple[str, str], dict] = {}
    for row in rows:
        title = str(row.get("title", "")).casefold()
        title = re.sub(
            r"\s*[-|–—]\s*(hong kong|hkg|shanghai|new york|nyc|london|singapore)\s*$",
            "",
            title,
        )
        key = (str(row.get("company", "")).casefold(), title)
        if not key[0] or not key[1]:
            continue
        existing = unique_by_role.get(key)
        if existing is None or _location_rank(
            str(row.get("location", "")), location
        ) > _location_rank(str(existing.get("location", "")), location):
            unique_by_role[key] = row
    unique = list(unique_by_role.values())
    return _rank_opportunities(unique, career_goal=career_goal, location=location)[:limit]
