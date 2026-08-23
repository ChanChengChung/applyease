"""Deterministic extraction of the contact block at the top of a CV.

Personal details are structured, privacy-sensitive facts, so they are never
guessed by the experience extraction model.
"""

from __future__ import annotations

import re


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d() .-]{6,}\d)(?!\w)")
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/[^\s|,;]+", re.I)
ADDRESS_RE = re.compile(r"^(?:address|地址|住址)\s*[:：-]\s*(.+)$", re.I)
EXPLICIT_LOCATION_RE = re.compile(r"^(?:location|based in|所在地|地点|地點)\s*[:：-]\s*(.+)$", re.I)
LOCATION_RE = re.compile(r"\b(?:hong kong(?: sar)?|kowloon|new territories|singapore|shanghai|beijing|london|new york|tokyo|sydney|vancouver|toronto)\b", re.I)
ADDRESS_HINT_RE = re.compile(
    r"\b(?:room|flat|unit|floor|building|hall|road|street|avenue|lane|district|estate|college|campus|tower|block)\b",
    re.I,
)
HEADING_RE = re.compile(r"^(?:education|experience|work experience|research experience|projects?|skills?|leadership|activities|contact|personal information)$", re.I)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" \t|·•,"))


def _candidate_name(lines: list[str]) -> str:
    for raw in lines[:8]:
        line = _clean(raw)
        if not line or len(line) > 80 or "@" in line or URL_RE.search(line):
            continue
        if PHONE_RE.search(line) or HEADING_RE.match(line):
            continue
        words = re.findall(r"[A-Za-z][A-Za-z'’-]*|[\u4e00-\u9fff]{2,4}", line)
        if 2 <= len(words) <= 5 and not LOCATION_RE.search(line):
            return line
    return ""


def _unlabelled_header_address(lines: list[str]) -> tuple[str, str]:
    """Recognise a conventional two-line CV address below the candidate name.

    Many CVs place an address such as ``Room 220, ...`` and ``Shatin, Hong
    Kong`` directly below the name rather than prefixing it with ``Address:``.
    We only inspect the short header before a contact line, which avoids
    accidentally turning an education or employment section into an address.
    """
    header_lines: list[str] = []
    for line in lines[:10]:
        if EMAIL_RE.search(line) or PHONE_RE.search(line) or URL_RE.search(line):
            break
        header_lines.append(line)

    candidates = [
        line
        for line in header_lines[1:]
        if ADDRESS_HINT_RE.search(line) or LOCATION_RE.search(line)
    ]
    if not candidates:
        return "", ""

    address = _clean(", ".join(candidates))
    location_line = next((line for line in reversed(candidates) if LOCATION_RE.search(line)), "")
    return address, _clean(location_line)


def extract_personal_information(text: str, source_file: str) -> dict | None:
    """Return an editable personal-profile Experience only for explicit facts."""
    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    header = "\n".join(lines[:18])
    details: list[str] = []
    name = _candidate_name(lines)
    if name:
        details.append(f"Name: {name}")
    email = EMAIL_RE.search(header)
    if email:
        details.append(f"Email: {email.group(0)}")
    phone = PHONE_RE.search(header)
    if phone:
        details.append(f"Phone: {_clean(phone.group(0))}")
    for line in lines[:25]:
        match = EXPLICIT_LOCATION_RE.match(line)
        if match:
            details.append(f"Location: {_clean(match.group(1))}")
            break
    for line in lines[:25]:
        match = ADDRESS_RE.match(line)
        if match:
            details.append(f"Address: {_clean(match.group(1))}")
            break
    # An unlabelled line mentioning a college can be education, not an address.
    # Only infer the conventional address block when a contact detail elsewhere
    # in the header proves that this is actually the CV contact section.
    has_contact_detail = bool(EMAIL_RE.search(header) or PHONE_RE.search(header) or URL_RE.search(header))
    if has_contact_detail:
        inferred_address, inferred_location = _unlabelled_header_address(lines)
        if not any(item.startswith("Address:") for item in details) and inferred_address:
            details.append(f"Address: {inferred_address}")
        if not any(item.startswith("Location:") for item in details) and inferred_location:
            details.append(f"Location: {inferred_location}")
    for url in URL_RE.findall(header):
        details.append(f"{'LinkedIn' if 'linkedin.com' in url.lower() else 'GitHub'}: {url}")
    # Do not turn education text into a personal profile: a name alone is not
    # enough.  Keep the record only if the CV explicitly exposes a contact or
    # location/address fact the user can review.
    if not any(
        item.startswith(prefix)
        for item in details
        for prefix in ("Email:", "Phone:", "Address:", "Location:", "LinkedIn:", "GitHub:")
    ):
        return None
    return {
        "title": name or "Personal information",
        "organization": "Personal profile",
        "description": "\n".join(dict.fromkeys(details)),
        "skills": [],
        "achievements": [],
        "source_file": source_file,
        "category": "personal",
        "confirmed": False,
    }
