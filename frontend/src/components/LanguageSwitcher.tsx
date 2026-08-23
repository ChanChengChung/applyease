import { useI18n } from "../i18n/LanguageProvider";
import { LANGUAGES } from "../i18n/index";

export function LanguageSwitcher() {
  const { language, setLanguage } = useI18n();

  return (
    <div className="lang-switcher" role="group" aria-label="Language">
      {LANGUAGES.map((item) => (
        <button
          key={item.code}

          type="button"

          className={language === item.code ? "active" : ""}

          aria-pressed={language === item.code}

          onClick={() => setLanguage(item.code)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
