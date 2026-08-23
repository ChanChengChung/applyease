import { useState } from "react";
import { StarterPlanner } from "../../components/StarterPlanner";
import { useT } from "../../i18n/LanguageProvider";

type Props = {
  onOpenExperienceBank: () => void;
  onOpenLearningPlan: () => void;
};

/** A deliberate entry screen for every signed-in user. */
export function WelcomePage({
  onOpenExperienceBank,
  onOpenLearningPlan,
}: Props) {
  const [path, setPath] = useState<"new" | null>(null);
  const t = useT();
  if (path === "new")
    return (
      <main className="welcome-page">
        <StarterPlanner
          mode="new"
          onChangeMode={() => setPath(null)}
          onOpenLearningPlan={onOpenLearningPlan}
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
          <p className="welcome-intro">{t("starter.welcomeSub")}</p>
        </header>
        <div className="onboarding-choice-grid">
          <button
            type="button"
            className="onboarding-choice-card newcomer"
            onClick={() => setPath("new")}
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
