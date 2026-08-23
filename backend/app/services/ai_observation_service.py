from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import ceil


def _rate(numerator: int, denominator: int) -> float:

    return round(numerator / denominator, 4) if denominator else 0.0


def _p95(values: list[int]) -> int:

    if not values:

        return 0
    ordered = sorted(values)

    return ordered[max(ceil(len(ordered) * 0.95) - 1, 0)]


def build_metrics(events: list, period_days: int) -> dict:
    outcomes = [event for event in events if event.event_type == "feature_outcome"]

    attempts = [event for event in events if event.event_type == "provider_attempt"]

    ai_successes = sum(event.status == "success" for event in outcomes)

    fallbacks = sum(event.status == "rule_fallback" for event in outcomes)

    errors = sum(event.status == "error" for event in outcomes)

    provider_groups: dict[str, list] = defaultdict(list)

    for event in attempts:
        provider_groups[event.provider].append(event)
    by_provider = []

    for provider, items in sorted(provider_groups.items()):
        success = sum(item.status == "success" for item in items)

        latencies = [item.latency_ms for item in items]

        by_provider.append(
            {
                "provider": provider,
                "attempts": len(items),
                "successes": success,
                "errors": len(items) - success,
                "success_rate": _rate(success, len(items)),
                "average_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
                "p95_latency_ms": _p95(latencies),
            }
        )

    feature_groups: dict[str, list] = defaultdict(list)

    for event in outcomes:
        feature_groups[event.feature].append(event)
    by_feature = []

    for feature, items in sorted(feature_groups.items()):
        success = sum(item.status == "success" for item in items)

        fallback = sum(item.status == "rule_fallback" for item in items)

        failed = sum(item.status == "error" for item in items)

        by_feature.append(
            {
                "feature": feature,
                "total": len(items),
                "ai_successes": success,
                "rule_fallbacks": fallback,
                "errors": failed,
                "success_rate": _rate(success, len(items)),
            }
        )

    recent = [
        {
            "feature": event.feature,
            "provider": event.provider,
            "model": event.model,
            "prompt_version": event.prompt_version,
            "status": event.status,
            "latency_ms": event.latency_ms,
            "error_category": event.error_category,
            "created_at": event.created_at,
        }
        for event in attempts[:20]
    ]

    return {
        "period_days": period_days,
        "generated_at": datetime.now(timezone.utc),
        "total_feature_calls": len(outcomes),
        "ai_successes": ai_successes,
        "rule_fallbacks": fallbacks,
        "errors": errors,
        "success_rate": _rate(ai_successes, len(outcomes)),
        "fallback_rate": _rate(fallbacks, len(outcomes)),
        "provider_attempts": len(attempts),
        "prompt_versions": sorted({event.prompt_version for event in events}),
        "by_provider": by_provider,
        "by_feature": by_feature,
        "recent_events": recent,
        "privacy_notice": "Only content-free operational metadata is stored; prompts, outputs, CV text, screenshots and API keys are never recorded.",
    }


def cutoff_for_days(days: int) -> datetime:

    return datetime.now(timezone.utc) - timedelta(days=days)
