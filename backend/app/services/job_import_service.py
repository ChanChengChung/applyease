"""Safe, review-first import of public job-page text; never persists a draft."""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx

from app.ai.providers import ProviderError, llm
from app.config import settings


def validate_public_job_url(value: str) -> str:
    parsed = urlparse(value.strip())

    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:

        raise ValueError("Only public HTTPS job-page URLs are allowed")
    try:
        if parsed.port not in (None, 443):
            raise ValueError("Only the standard HTTPS port is allowed")
    except ValueError as exc:
        raise ValueError("Only the standard HTTPS port is allowed") from exc

    try:
        addresses = {
            row[4][0] for row in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        }

    except OSError as exc:

        raise ValueError("Could not resolve the job-page host") from exc

    if any(not ipaddress.ip_address(address).is_global for address in addresses):

        raise ValueError("Private, local and reserved hosts are not allowed")

    # URL fragments are never sent in HTTP requests; dropping them also keeps
    # the displayed source URL unambiguous after a review-first import.
    return parsed._replace(fragment="").geturl()


# Backwards-compatible private alias for existing integrations/tests.
_public_https_url = validate_public_job_url


def _verify_connected_peer(response: httpx.Response) -> None:
    """Fail closed in production if the actual peer is not public.

    DNS can change between our allow-list resolution and a client's connect.
    httpx/httpcore exposes the established peer stream; checking it prevents a
    resolver race from silently reaching loopback or an RFC1918 address.
    """
    stream = getattr(response, "extensions", {}).get("network_stream")
    address = stream.get_extra_info("server_addr") if stream is not None else None
    if not address:
        if settings.app_env == "production":
            raise ValueError("Could not verify the public job-page connection")
        return
    try:
        peer_ip = ipaddress.ip_address(str(address[0]))
    except (ValueError, TypeError, IndexError) as exc:
        raise ValueError("Could not verify the public job-page connection") from exc
    if not peer_ip.is_global:
        raise ValueError("The job page connection resolved to a private or reserved host")


def _text(value: str) -> str:
    # Metadata is extracted from the original HTML below. Keeping the document
    # head in the job description otherwise repeats the browser title as the
    # first "requirement" (a common issue on JavaScript career sites).
    value = re.sub(r"(?is)<head\b.*?</head>", " ", value)
    value = re.sub(r"(?is)<(script|style|noscript|svg).*?>.*?</\1>", " ", value)

    value = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|section|article)>", "\n", value)

    value = re.sub(r"(?s)<[^>]+>", " ", value)

    text = re.sub(r"[ \t]+", " ", html.unescape(value)).replace(" \n", "\n").strip()
    return _job_body_text(text)[: settings.max_job_import_characters]


_JOB_START_MARKERS = (
    "about the position",
    "about the role",
    "job description",
    "what you'll do",
    "what you will do",
    "responsibilities",
    "the role",
)
_JOB_END_MARKERS = (
    "equal opportunity employer",
    "equal employment opportunity",
    "helpful links",
    "disclosures and policies",
    "privacy policy",
    "all rights reserved",
    "if you'd like to learn more",
    "if you would like to learn more",
    "learn more about our interview process",
)
_PAGE_NOISE = re.compile(
    r"(?:uses cookies|cookie policy|accept all|reject all|mobile navigation|"
    r"menu toggle|who we are|what we do|the latest|street view|open roles|"
    r"programs and events|join jane street|contact us|share this job|"
    r"disclosures? (?:&|and) policies|fraud and impersonation|copyright|©\s*\d{4}|"
    r"regulated activities)",
    re.I,
)


def _job_body_text(value: str) -> str:
    """Keep the role narrative and discard career-site chrome/footer deterministically."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    # Navigation labels are short, while a legitimate sentence can naturally
    # say "Join Jane Street". Cookie notices are always noise regardless of
    # length; the rest of the chrome rule is intentionally restricted to
    # compact labels to avoid dropping a real responsibility sentence.
    lines = [
        line
        for line in lines
        if line
        and not (
            "uses cookies" in line.casefold()
            or "cookie policy" in line.casefold()
            or (len(line) <= 50 and _PAGE_NOISE.search(line))
        )
    ]
    if not lines:
        return ""
    start = next((i for i, line in enumerate(lines) if line.casefold() in _JOB_START_MARKERS), None)
    if start is not None:
        lines = lines[start:]
    end = next(
        (
            i
            for i, line in enumerate(lines)
            if i > 0 and any(marker in line.casefold() for marker in _JOB_END_MARKERS)
        ),
        None,
    )
    if end is not None:
        lines = lines[:end]
    deduped: list[str] = []
    seen_short: set[str] = set()
    for line in lines:
        key = line.casefold()
        if len(line) <= 35 and key in seen_short:
            continue
        if len(line) <= 35:
            seen_short.add(key)
        deduped.append(line)
    return "\n".join(deduped)


def _normalise_for_grounding(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _grounded_llm_job_body(value: str) -> str:
    """Layer 3: constrained LLM review, with deterministic provenance checks.

    The model is an editor, never a source of facts. If it paraphrases,
    hallucinates, times out, or returns an empty answer, the prior rule-based
    extraction remains the result.
    """
    if not settings.ai_job_analysis_enabled or len(value) < 80:
        return value
    source = value[: min(len(value), 24000)]
    prompt = f"""You clean a single already-sanitised job posting for ApplyEase.
Return JSON only: {{"job_description": "..."}}.
Copy only the role's actual responsibilities, team/work description, required or preferred qualifications, and eligibility. Keep useful headings when present. Exclude application instructions, links, benefits/perks, travel/accommodation, interview-process promotion, equal-opportunity/legal text, and company navigation.
Do not summarise, paraphrase, infer, or add facts. Every non-empty output line must be copied verbatim from SOURCE.

SOURCE:
{source}
"""
    try:
        result = llm.generate_json(
            prompt,
            {
                "type": "object",
                "properties": {"job_description": {"type": "string"}},
                "required": ["job_description"],
            },
            feature="job_import_review",
            prompt_version="job-import-v1",
        )
        candidate = str(result.get("job_description") or "").strip()
        lines = [line.strip() for line in candidate.splitlines() if line.strip()]
        source_norm = _normalise_for_grounding(source)
        if not lines or len(candidate) < 20 or len(candidate) > len(source) + 20:
            return value
        # Headings can be short; substantive output must be verbatim source
        # material after whitespace normalisation.
        if any(
            len(line) > 24 and _normalise_for_grounding(line) not in source_norm for line in lines
        ):
            return value
        return "\n".join(lines)
    except ProviderError:
        return value


def _meta(page: str, key: str) -> str:
    for tag in re.findall(r"(?is)<meta\b[^>]*>", page):
        name = re.search(r"(?is)(?:property|name)\s*=\s*['\"]([^'\"]+)", tag)
        content = re.search(r"(?is)content\s*=\s*['\"]([^'\"]+)", tag)
        if name and content and name.group(1).casefold() == key.casefold():
            return html.unescape(content.group(1)).strip()
    return ""


def _clean_title(value: str) -> str:
    """Strip common job-board branding without losing a real role title."""
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(
        r"\s+[|·—–-]\s+(?:careers?|jobs?|job board|greenhouse|lever)\b.*$", "", value, flags=re.I
    )
    return value.strip(" |·—–-")[:200]


def _job_postings(page: str) -> list[dict]:
    """Read public JSON-LD JobPosting records without trusting page chrome."""
    postings: list[dict] = []
    for raw in re.findall(
        r"(?is)<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", page
    ):
        try:
            import json

            data = json.loads(html.unescape(raw).strip())
        except (ValueError, TypeError):
            continue
        rows = (
            data
            if isinstance(data, list)
            else data.get("@graph", [data]) if isinstance(data, dict) else []
        )
        for item in rows:
            types = item.get("@type", "") if isinstance(item, dict) else ""
            type_values = types if isinstance(types, list) else [types]
            if isinstance(item, dict) and any(
                str(value).casefold() == "jobposting" for value in type_values
            ):
                postings.append(item)
    return postings


def _json_ld_job(page: str) -> tuple[str, str]:
    """Prefer structured JobPosting title and organisation when supplied."""
    for item in _job_postings(page):
        title = str(item.get("title") or "").strip()
        org = item.get("hiringOrganization") or {}
        company = str(org.get("name") or "").strip() if isinstance(org, dict) else str(org).strip()
        if title or company:
            return _clean_title(title), company[:200]
    return "", ""


def _json_ld_description(page: str) -> str:
    """Layer 1: use a role's own structured description when it is present."""
    for item in _job_postings(page):
        value = str(item.get("description") or "").strip()
        if len(value) >= 20:
            cleaned = _text(value)
            if len(cleaned) >= 20:
                return cleaned
    return ""


_TITLE_SEPARATORS = (" :: ", "::", " | ", " · ", " — ", " – ")


def _split_role_and_company(value: str) -> tuple[str, str]:
    """Read common ATS browser-title conventions.

    Greenhouse frequently uses ``Role, Location :: Company`` while several
    other boards use ``Role | Company``. Split from the right so a role name
    containing punctuation is preserved.
    """
    value = re.sub(r"\s+", " ", value).strip()
    for separator in _TITLE_SEPARATORS:
        if separator in value:
            role, company = value.rsplit(separator, 1)
            if role.strip() and company.strip():
                return role.strip(), company.strip()
    return value, ""


def _strip_location_from_role(value: str) -> str:
    """Remove an ATS title's trailing location, not role qualifications."""
    value = re.sub(
        r",\s*(?:hong\s+kong|singapore|london|new\s+york(?:\s*,\s*ny)?|"
        r"tokyo|sydney|remote|hybrid)\s*$",
        "",
        value,
        flags=re.I,
    )
    return value.strip()


def _company_from_title(value: str) -> str:
    return _split_role_and_company(value)[1][:200]


def _role_from_title(value: str) -> str:
    """Use the role half only when a browser title actually looks like a job."""
    role, company = _split_role_and_company(value)
    if company and re.search(
        r"\b(intern|engineer|researcher|analyst|developer|associate|manager|designer|trader)\b",
        role,
        re.I,
    ):
        return _clean_title(_strip_location_from_role(role))
    return _clean_title(value)


def draft_from_text(text: str, source_url: str = "") -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    head = " ".join(lines[:4])

    title = _clean_title(
        next(
            (
                line
                for line in lines[:12]
                if re.search(
                    r"\b(intern|engineer|researcher|analyst|developer|associate)\b", line, re.I
                )
            ),
            "Untitled role",
        )
    )

    company_match = re.search(r"\b(?:at|join)\s+([A-Z][\w .,&'-]{1,80})", head)

    company = company_match.group(1).strip(" .,-") if company_match else ""

    location_match = re.search(r"\b(?:location|based in)\s*[:\-]?\s*([^\n|]{2,100})", text, re.I)

    deadline_match = re.search(
        r"\b(?:deadline|apply by|closing date)\s*[:\-]?\s*([^\n|]{3,80})", text, re.I
    )

    return {
        "title": title,
        "company": company,
        "description": text[: settings.max_job_import_characters],
        "location": location_match.group(1).strip() if location_match else "",
        "deadline": deadline_match.group(1).strip() if deadline_match else "",
        "source_url": source_url,
    }


def import_public_job_page(raw_url: str) -> dict[str, str | bool]:
    # Keep this indirection for testability and backwards compatibility with
    # earlier integrations that supplied a validated URL seam.
    url = _public_https_url(raw_url)

    try:

        with httpx.stream(
            "GET",
            url,
            timeout=settings.job_import_timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "ApplyEaseJobImporter/1.0 (+local user initiated)"},
            trust_env=False,
        ) as response:

            _verify_connected_peer(response)

            if response.is_redirect:

                raise ValueError(
                    "Redirecting job pages are not imported; open the final public HTTPS URL and try again"
                )

            if (
                response.status_code != 200
                or "html" not in response.headers.get("content-type", "").casefold()
            ):

                raise ValueError("The URL must return a public HTML job page")
            declared_size = response.headers.get("content-length")

            if (
                declared_size
                and declared_size.isdigit()
                and int(declared_size) > settings.max_job_import_bytes
            ):

                raise ValueError("The job page exceeds the import size limit")
            chunks: list[bytes] = []
            received = 0

            for chunk in response.iter_bytes():
                received += len(chunk)

                if received > settings.max_job_import_bytes:

                    raise ValueError("The job page exceeds the import size limit")
                chunks.append(chunk)
            page = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")

    except httpx.HTTPError as exc:

        raise ValueError("Could not retrieve this public job page") from exc
    # Read the page metadata before assessing the body. Modern career sites
    # commonly return an HTML application shell and render the description in
    # the browser.  In that case we can still prefill a reviewable draft and
    # ask the user to paste the JD, rather than failing the entire import.
    structured_title, structured_company = _json_ld_job(page)
    page_title = _meta(page, "og:title") or _meta(page, "twitter:title")
    document_title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    document_title = _text(document_title_match.group(1)) if document_title_match else ""
    title_candidate = (
        structured_title or _role_from_title(page_title) or _role_from_title(document_title)
    )
    company_candidate = (
        structured_company
        or _meta(page, "og:site_name")
        or _meta(page, "twitter:site")
        or _company_from_title(page_title)
        or _company_from_title(document_title)
    )
    # Layer 1: standard JobPosting JSON-LD description; layer 2: cleaned
    # visible HTML. Layer 3 then performs a grounded, fail-safe review.
    text = _grounded_llm_job_body(_json_ld_description(page) or _text(page))
    if len(text) >= 20:
        draft: dict[str, str | bool] = draft_from_text(text, url)
    else:
        draft = {
            "title": "Untitled role",
            "company": "",
            "description": "",
            "location": "",
            "deadline": "",
            "source_url": url,
            "needs_manual_description": True,
        }
    if title_candidate:
        draft["title"] = title_candidate
    if company_candidate:
        draft["company"] = company_candidate.lstrip("@").strip()[:200]

    return draft
