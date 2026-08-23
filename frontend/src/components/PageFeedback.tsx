export type FeedbackKind = "success" | "error" | "info";

export function PageFeedback({
  kind,
  message,
  actionLabel,
  onAction,
}: {
  kind: FeedbackKind;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  const role = kind === "error" ? "alert" : "status";

  return (
    <div
      className={`feedback feedback-${kind}`}
      role={role}
      aria-live={kind === "error" ? "assertive" : "polite"}
    >
      <span className={kind === "error" ? "error" : undefined}>{message}</span>
      {actionLabel && onAction && (
        <button onClick={onAction}>{actionLabel}</button>
      )}
    </div>
  );
}
