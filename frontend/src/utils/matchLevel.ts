export type MatchLevel = "low" | "medium" | "high" | "veryHigh";

/** Convert the internal 0–100 score into the user-facing readiness band. */
export function matchLevelForScore(score: number): MatchLevel {
  if (score < 40) return "low";
  if (score < 60) return "medium";
  if (score < 80) return "high";
  return "veryHigh";
}
