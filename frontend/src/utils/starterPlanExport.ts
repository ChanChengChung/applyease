import type { StarterPlan } from "../types/resource";

/** Export the persisted starter plan as a portable Markdown file. */
export function downloadStarterPlan(plan: StarterPlan) {
  const body = [
    `# ${plan.headline}`,
    "",
    "## First action",
    plan.first_action,
    "",
    "## Milestones",
    ...plan.milestones.map((item, index) => `${index + 1}. ${item}`),
    "",
    "## Recommended resources",
    ...plan.resources.map(
      (item) =>
        `- [${item.title}](${item.url}) — ${item.provider}: ${item.description}`,
    ),
  ].join("\n");
  const blob = new Blob([body], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "applyease-starter-plan.md";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
