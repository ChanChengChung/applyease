import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import {
  DEFAULT_LANGUAGE,
  detectLanguage,
  saveLanguage,
  translate,
} from "./index";
import type { Language } from "./index";

type Vars = Record<string, string | number>;

type I18nContextValue = {
  language: Language;

  setLanguage: (language: Language) => void;

  t: (key: string, vars?: Vars) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() =>
    detectLanguage(),
  );

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next);

    saveLanguage(next);

    document.documentElement.lang =
      next === "zh-CN" ? "zh-CN" : next === "zh-TW" ? "zh-TW" : "en";
  }, []);

  useEffect(() => {
    const applyPathLanguage = () => {
      const next = detectLanguage();
      setLanguageState(next);
      document.documentElement.lang =
        next === "zh-CN" ? "zh-CN" : next === "zh-TW" ? "zh-TW" : "en";
    };
    applyPathLanguage();
    window.addEventListener("popstate", applyPathLanguage);
    return () => window.removeEventListener("popstate", applyPathLanguage);
  }, []);

  const t = useCallback(
    (key: string, vars?: Vars) => translate(language, key, vars),
    [language],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ language, setLanguage, t }),
    [language, setLanguage, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);

  if (!ctx) throw new Error("useI18n must be used within a LanguageProvider");

  return ctx;
}

export function useT(): (key: string, vars?: Vars) => string {
  return useI18n().t;
}
