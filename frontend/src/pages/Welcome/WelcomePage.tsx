import { useState } from "react";
import { StarterPlanner } from "../../components/StarterPlanner";
import { useT } from "../../i18n/LanguageProvider";

type Props = {
  onOpenExperienceBank: () => void;
  onOpenLearningPlan: () => void;
  onPathChange?: (path: "new" | null) => void;
  initialPath?: "new" | null;
};

/** A deliberate entry screen for every signed-in user. */
export function WelcomePage({
  onOpenExperienceBank,
  onOpenLearningPlan,
  onPathChange,
  initialPath = null,
}: Props) {
  const [path, setPath] = useState<"new" | null>(initialPath);
  const t = useT();
  const chooseNewPath = () => {
    setPath("new");
    onPathChange?.("new");
  };
  const leaveNewPath = () => {
    setPath(null);
    onPathChange?.(null);
  };
  if (path === "new")
    return (
      <main className="welcome-page">
        <StarterPlanner
          mode="new"
          onChangeMode={leaveNewPath}
          onOpenLearningPlan={onOpenLearningPlan}
          showSavedPlans={false}
        />
      </main>
    );

  return (
    <main className="welcome-page">
      <section className="onboarding-choice" aria-labelledby="onboarding-title">
        <header className="onboarding-choice-heading">
          <p className="welcome-brand" aria-label="ApplyEase welcome">
            <span className="welcome-brand-name">APPLY<span>EASE</span></span>
            <span className="welcome-brand-divider" aria-hidden="true" />
            <span className="welcome-brand-welcome">WELCOME</span>
          </p>
          <h1 id="onboarding-title">{t("starter.welcomeTitle")}</h1>
        </header>
        <div className="onboarding-choice-grid">
          <button
            type="button"
            className="onboarding-choice-card newcomer"
            onClick={chooseNewPath}
          >
            <span aria-hidden="true">✦</span>
            <strong>{t("starter.path.new.title")}</strong>
            <small>{t("starter.path.new.sub")}</small>
            <em>{t("starter.path.new.action")} →</em>
          </button>
          <button
            type="button"
            className="onboarding-choice-card experienced"
            onClick={onOpenExperienceBank}
          >
            <span aria-hidden="true">▣</span>
            <strong>{t("starter.path.experienced.title")}</strong>
            <small>{t("starter.path.experienced.sub")}</small>
            <em>{t("starter.path.experienced.action")} →</em>
          </button>
        </div>
      </section>
    </main>
  );
}
