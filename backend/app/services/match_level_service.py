"""One public match-band policy for every scored ApplyEase surface."""

from typing import Literal

MatchLevel = Literal["low", "medium", "high", "very_high"]


def match_level_for_score(score: int | float | None) -> MatchLevel:
    """Map an internal 0–100 score to the only user-facing match bands."""
    value = max(0, min(100, int(score or 0)))
    if value < 40:
        return "low"
    if value < 60:
        return "medium"
    if value < 80:
        return "high"
    return "very_high"
