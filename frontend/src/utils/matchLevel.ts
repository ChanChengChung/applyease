export type MatchLevel = "low" | "medium" | "high" | "very_high";

/** Convert the internal 0–100 score into the user-facing readiness band. */
export function matchLevelForScore(score: number): MatchLevel {
  if (score < 40) return "low";
  if (score < 60) return "medium";
  if (score < 80) return "high";
  return "very_high";
}

/** Prefer the server-calculated band; scoring is only a legacy API fallback. */
export function resolveMatchLevel(
  level: MatchLevel | undefined,
  score: number,
): MatchLevel {
  return level ?? matchLevelForScore(score);
}

/** Job-analysis translations predate the snake_case API contract. */
export function matchLevelTranslationKey(level: MatchLevel): string {
  return level === "very_high" ? "veryHigh" : level;
}
