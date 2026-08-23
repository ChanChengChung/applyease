import re

from app.ai.providers import ProviderError
from app.services.answer_template_service import AnswerTemplate, resolve_template

QUESTION_PATTERNS = [
    (
        "company_interest",
        ["why our company", "why this company", "what attracts you", "join our company"],
    ),
    ("motivation", ["why are you interested", "why this role", "why do you want"]),
    ("project", ["describe a project", "tell us about a project", "project you are proud"]),
    ("teamwork", ["team", "collaborat", "conflict"]),
    ("leadership", ["leadership", "led a", "led an", "leader"]),
    ("technical", ["technical", "algorithm", "programming", "code", "model", "skills"]),
    ("challenge", ["challeng", "difficult", "failure", "setback"]),
    ("education", ["university", "school", "degree", "major", "graduation"]),
    (
        "identity",
        [
            "passport",
            "hkid",
            "identity document",
            "national id",
            "date of birth",
            "nationality",
            "citizenship",
        ],
    ),
    (
        "personal_info",
        ["full name", "email", "e-mail", "phone", "telephone", "address", "linkedin"],
    ),
    (
        "eligibility",
        ["work authorization", "authorised to work", "authorized to work", "visa", "sponsorship"],
    ),
    ("salary", ["salary", "compensation", "expected pay"]),
    ("demographic", ["gender", "ethnicity", "race", "disability", "health"]),
    ("availability", ["available to start", "start date", "notice period"]),
]

MANUAL_TYPES = {"identity", "personal_info", "eligibility", "salary", "demographic", "availability"}
SENSITIVE_TYPES = {"identity", "eligibility", "salary", "demographic"}
FIELD_LABEL_RE = re.compile(
    r"^(?:full name|name|email|e-mail|phone|telephone|address|linkedin|passport(?: number)?|hkid(?: number)?|identity document(?: number)?|national id(?: number)?|date of birth|nationality|citizenship|university|school|degree|major|graduation(?: date| year)?|skills|"
    r"work authori[sz]ation|visa(?: status)?|sponsorship|salary(?: expectation)?|compensation|gender|ethnicity|race|"
    r"disability|health|available start date|notice period)\s*[:*]?\s*$",
    re.I,
)


def classify_question(question: str) -> str:
    lower = question.lower()

    for question_type, patterns in QUESTION_PATTERNS:

        if any(pattern in lower for pattern in patterns):
            return question_type

    return "general"


def field_metadata(
    question: str, question_type: str, limit_unit: str = "characters", max_words: int | None = None
) -> dict:
    lower = question.casefold()

    field_key = re.sub(r"[^a-z0-9]+", "_", lower).strip("_")[:80] or "field"

    input_type = (
        "email"
        if "email" in lower or "e-mail" in lower
        else (
            "tel"
            if "phone" in lower or "telephone" in lower
            else "textarea" if question_type not in MANUAL_TYPES else "text"
        )
    )

    short_factual_field = bool(FIELD_LABEL_RE.match(question)) and question_type in {
        "education",
        "technical",
    }

    return {
        "field_key": field_key,
        "input_type": input_type,
        "sensitive": question_type in SENSITIVE_TYPES,
        "requires_user_input": question_type in MANUAL_TYPES or short_factual_field,
        "limit_unit": limit_unit,
        "max_words": max_words,
    }


def parse_limit(text: str, question: str) -> tuple[int, str, int | None]:
    position = text.casefold().find(question.casefold())

    # A limit written on the same line is authoritative. Looking backwards first
    # can accidentally assign the previous field's limit to this question.
    window = question

    if (
        not re.search(
            r"(?:maximum|max|limit|up to|within|不超过|最多)\s*(?:of\s*)?\d{1,5}", window, re.I
        )
        and position >= 0
    ):
        window = text[position : position + len(question) + 180]

    match = re.search(
        r"(?:maximum|max|limit|up to|within|不超过|最多)\s*(?:of\s*)?(\d{1,5})\s*(characters?|chars?|字(?:符)?|words?|词)?",
        window,
        re.I,
    )

    if not match:
        return 300, "characters", None

    value = int(match.group(1))
    unit = (match.group(2) or "characters").casefold()

    if "word" in unit or "词" in unit:
        words = min(max(value, 1), 1000)

        return min(max(words * 8, 50), 5000), "words", words

    return min(max(value, 20), 5000), "characters", None


def detect_questions(text: str) -> list[dict]:
    questions: list[dict] = []

    for line in text.splitlines():
        clean = re.sub(r"^\s*(?:[-•●▪\d.)]+\s*)", "", line).strip()

        if not clean or len(clean) > 1000:
            continue

        is_question = (
            "?" in clean
            or "？" in clean
            or bool(
                re.match(
                    r"^(why|what|how|describe|tell us|please describe|are you|do you|when)",
                    clean,
                    re.I,
                )
            )
            or bool(FIELD_LABEL_RE.match(clean))
        )

        if not is_question:
            continue

        question_type = classify_question(clean)

        max_characters, unit, max_words = parse_limit(text, clean)

        metadata = field_metadata(clean, question_type, unit, max_words)

        questions.append(
            {
                "question": clean[:3000],
                "question_type": question_type,
                "max_characters": max_characters,
                "required": not any(
                    word in clean.casefold()
                    for word in ["optional", "if applicable", "如适用", "可选"]
                ),
                "answer": {"metadata": metadata},
            }
        )
    unique: list[dict] = []
    seen: set[str] = set()

    for item in questions:
        key = re.sub(r"\W+", "", item["question"].casefold())

        if key and key not in seen:
            unique.append(item)
            seen.add(key)

    if not unique:

        raise ValueError("No application questions or recognizable form fields were found.")

    return unique[:50]


def is_manual_question(question) -> bool:
    metadata = (question.answer or {}).get("metadata", {})

    return bool(metadata.get("requires_user_input")) or question.question_type in MANUAL_TYPES


def max_words_for(question) -> int | None:
    value = (question.answer or {}).get("metadata", {}).get("max_words")

    return int(value) if isinstance(value, int) and value > 0 else None


def trim_to_word_limit(text: str, max_words: int | None) -> str:

    if not max_words:
        return text

    matches = list(re.finditer(r"\S+", text))

    return text if len(matches) <= max_words else text[: matches[max_words - 1].end()].rstrip()


def analyze_application_form(raw_text: str, *, ai_enabled: bool) -> list[dict]:
    """Application-facing form analysis boundary; provider selection stays out of routes."""

    normalized = raw_text.strip()

    if len(normalized) < 10:

        raise ValueError("Application form text must contain at least 10 non-whitespace characters")

    if len(normalized) > 50_000:

        raise ValueError("Application form text exceeds the 50,000-character limit")

    if ai_enabled:
        from app.ai.application_form_analyzer import analyze_form_safe

        return analyze_form_safe(normalized)

    return detect_questions(normalized)


def extract_screenshot_text(data: bytes, mime_type: str) -> str:
    """OCR is intentionally isolated so the API can enforce consent before calling it."""

    import time

    from app.ai.observability import ai_trace, error_category, record_event, record_outcome

    from app.ai.prompt_versions import SCREENSHOT_OCR

    from app.config import settings

    from app.ai.providers import llm

    with ai_trace("screenshot_ocr", SCREENSHOT_OCR, len(data)) as trace:
        started = time.monotonic()

        try:
            text = llm.providers["gemini"].extract_image_text(data, mime_type)

            latency = round((time.monotonic() - started) * 1000)

            record_event(
                trace=trace,
                event_type="provider_attempt",
                provider="gemini",
                model=settings.gemini_model,
                status="success",
                latency_ms=latency,
                output_characters=len(text),
            )
            record_outcome(status="success", provider="gemini")

            return text

        except KeyError as exc:
            record_outcome(status="error", provider="gemini", category="unsupported_provider")

            raise ProviderError("Gemini OCR provider is not configured") from exc

        except ProviderError as exc:
            latency = round((time.monotonic() - started) * 1000)

            record_event(
                trace=trace,
                event_type="provider_attempt",
                provider="gemini",
                model=settings.gemini_model,
                status="error",
                latency_ms=latency,
                category=error_category(exc),
            )
            record_outcome(status="error", provider="gemini", category=error_category(exc))

            raise


def generate_question_answer(
    job,
    question,
    experiences,
    *,
    ai_enabled: bool,
    template: AnswerTemplate = "auto",
    output_language: str = "en",
    answer_tone: str = "professional",
    desired_content: str = "",
    db=None,
    user_id: int | None = None,
):

    if is_manual_question(question):

        return None

    effective_template, target_characters = resolve_template(
        template, question.question_type, question.max_characters
    )

    if ai_enabled:
        from app.ai.material_generator import generate_answer_safe

        return generate_answer_safe(
            job,
            question.question,
            target_characters,
            experiences,
            template=effective_template,
            output_language=output_language,
            answer_tone=answer_tone,
            desired_content=desired_content,
            db=db,
            user_id=user_id,
        )
    from app.services.material_service import generate_answer

    return generate_answer(
        job,
        question.question,
        target_characters,
        experiences,
        template=effective_template,
        output_language=output_language,
        answer_tone=answer_tone,
        desired_content=desired_content,
    )
