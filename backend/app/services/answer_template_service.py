from __future__ import annotations

from typing import Literal

AnswerTemplate = Literal["auto", "concise_50", "standard_150", "detailed_300", "star"]

TEMPLATE_CHARACTER_TARGETS = {
    "concise_50": 50,
    "standard_150": 150,
    "detailed_300": 300,
    "star": 300,
}
BEHAVIOURAL_TYPES = {"project", "teamwork", "leadership", "challenge"}


def recommended_template(question_type: str, max_characters: int) -> AnswerTemplate:
    """Choose a useful default without ever overriding a form's own limit."""
    if max_characters <= 80:
        return "concise_50"
    if question_type in BEHAVIOURAL_TYPES and max_characters >= 180:
        return "star"
    if max_characters <= 180:
        return "standard_150"
    return "detailed_300"


def resolve_template(
    template: AnswerTemplate, question_type: str, max_characters: int
) -> tuple[AnswerTemplate, int]:
    effective = (
        recommended_template(question_type, max_characters) if template == "auto" else template
    )
    return effective, min(TEMPLATE_CHARACTER_TARGETS[effective], max_characters)


def template_instruction(template: AnswerTemplate) -> str:
    rules = {
        "concise_50": "Use one direct, high-signal sentence. Do not add an introduction or conclusion.",
        "standard_150": "Write a concise, specific response in one short paragraph.",
        "detailed_300": "Write a focused response with concrete, cited evidence; do not pad it with generic claims.",
        "star": "Use clearly labelled Situation, Task, Action, and Result sections. Keep each section concise and only use supplied evidence.",
    }
    return rules[template]


def evaluate_template(text: str, template: AnswerTemplate, target_characters: int) -> list[str]:
    """Return non-blocking quality signals; hard form limits remain enforced elsewhere."""
    warnings: list[str] = []
    if len(text) > target_characters:
        warnings.append(f"答案超過所選模板的 {target_characters} 字元建議。")
    if template == "star":
        lowered = text.casefold()
        labels = (
            ("situation", "情境", "背景"),
            ("task", "任務"),
            ("action", "行動"),
            ("result", "結果"),
        )
        missing = [
            english.title()
            for english, *alternatives in labels
            if not any(label in lowered for label in (english, *alternatives))
        ]
        if missing:
            warnings.append("STAR 結構不完整：缺少 " + ", ".join(missing) + "。")
    return warnings
