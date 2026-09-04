import { useEffect, useState } from "react";
import type { Material } from "../types/material";
import { useT } from "../i18n/LanguageProvider";

export function MaterialEditor({
  material,
  onSave,
  onDraftChange,
}: {
  material: Material;
  onSave: (text: string) => Promise<void>;
  /** Lets the resume preview render each keystroke before the user saves. */
  onDraftChange?: (text: string) => void;
}) {
  const [draft, setDraft] = useState(material.text);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const t = useT();

  useEffect(() => {
    setDraft(material.text);
    onDraftChange?.(material.text);
    setError("");
    setCopied(false);
  }, [material.id, material.text, onDraftChange]);

  const save = async () => {
    if (!draft.trim()) return;
    setSaving(true);
    setError("");
    try {
      await onSave(draft.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : t("shared.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(draft);
      setCopied(true);
    } catch {
      setError(t("shared.copyFailed"));
    }
  };

  const exportText = () => {
    const type = material.material_type.replace(/[^a-z0-9]+/gi, "-") || "material";
    const blob = new Blob([draft], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `ApplyEase-${type}.txt`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const overLimit = Boolean(
    material.max_characters && draft.length > material.max_characters,
  );

  const methodLabel =
    material.generation_method === "ai"
      ? t("shared.generationMethod.ai")
      : material.generation_method === "user_edited"
        ? t("shared.generationMethod.user")
        : t("shared.generationMethod.rule");

  const factLabel = material.fact_check_passed
    ? t("shared.factPass")
    : t("shared.factReview");

  return (
    <div className="card material-editor-card">
      <div className="material-editor-heading">
        <div>
          <p className="section-kicker">APPLYEASE · MATERIAL EDITOR</p>
          <h2>
            {material.material_type === "resume"
              ? t("shared.resume")
              : material.material_type}
          </h2>
        </div>
        <span
          className={
            material.fact_check_passed
              ? "editor-status pass"
              : "editor-status review"
          }
        >
          {factLabel}
        </span>
      </div>
        {material.material_type === "resume" ? (
          <aside className="resume-tailoring-note">
            <strong>{t("material.aiTailoringTitle")}</strong>
            <span>
              {material.generation_method === "ai"
                ? t("material.aiTailoringAi")
                : t("material.aiTailoringFallback")}
            </span>
          </aside>
        ) : (
          <p>
            <small>
              {t("shared.generationMethod")}：{methodLabel}
            </small>
          </p>
        )}
      <label>
        {t("material.editorLabel")}
        <textarea
          className="material-text"
          aria-label={t("material.editorLabel")}
          value={draft}
          onChange={(event) => {
            const next = event.target.value;
            setDraft(next);
            onDraftChange?.(next);
            setCopied(false);
          }}
        />
      </label>
      <p>
        {t("shared.charCount", { n: draft.length })}
        {material.max_characters ? `/${material.max_characters}` : ""} ·{" "}
        {t("shared.factCheck", { status: factLabel })}
      </p>
      {overLimit && <p className="error">{t("shared.overLimit")}</p>}
      {material.warnings.map((warning) => (
        <p className="error" key={warning}>
          {warning}
        </p>
      ))}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="actions">
        <button
          disabled={
            saving || !draft.trim() || overLimit || draft === material.text
          }
          onClick={() => void save()}
        >
          {saving ? t("shared.saving") : t("shared.saveEdit")}
        </button>
        <button onClick={() => void copy()}>
          {copied ? t("shared.copied") : t("shared.copy")}
        </button>
        <button onClick={exportText}>{t("shared.exportText")}</button>
      </div>
    </div>
  );
}
