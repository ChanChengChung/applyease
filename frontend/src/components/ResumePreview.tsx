import type { ResumeAppearance, ResumeTemplate } from "../types/material";
import { useT } from "../i18n/LanguageProvider";

export type ResumeSection = { name: string; lines: string[] };

export function splitResumeSections(text: string): ResumeSection[] {
  const result: ResumeSection[] = [];
  let current: ResumeSection | null = null;
  const preface: string[] = [];

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;

    const isHeading =
      line.length <= 50 && line === line.toUpperCase() && /[A-Z]/.test(line);

    if (isHeading) {
      current = { name: line.replace(/:$/, ""), lines: [line] };
      result.push(current);
    } else if (current) current.lines.push(line);
    else preface.push(line);
  }

  if (preface.length)
    result.unshift({ name: "Resume summary", lines: preface });

  return result.length
    ? result
    : [{ name: "Resume", lines: [text.trim() || "No resume content"] }];
}

export function ResumePreview({
  text,
  displayName,
  contactLine,
  contact,
  template,
  appearance,
  order,
  hidden,
}: {
  text: string;
  displayName: string;
  contactLine: string;
  contact?: {
    email?: string;
    phone?: string;
    location?: string;
    linkedinUrl?: string;
    githubUrl?: string;
  };
  template: ResumeTemplate;
  appearance?: ResumeAppearance;
  order: string[];
  hidden: string[];
}) {
  const t = useT();

  const contactRows = [
    [
      contact?.location,
      contact?.phone ? `Phone: ${contact.phone}` : "",
      contact?.email ? `Email: ${contact.email}` : "",
    ]
      .filter(Boolean)
      .join("  |  "),
    [
      contact?.linkedinUrl ? `LinkedIn: ${contact.linkedinUrl}` : "",
      contact?.githubUrl ? `GitHub: ${contact.githubUrl}` : "",
    ]
      .filter(Boolean)
      .join("  |  "),
  ].filter(Boolean);
  if (!contactRows.length && contactLine) contactRows.push(contactLine);

  const sections = splitResumeSections(text);
  const map = new Map(sections.map((item) => [item.name, item]));

  const ordered = [
    ...order.filter((name) => map.has(name)),
    ...sections
      .map((item) => item.name)
      .filter((name) => !order.includes(name)),
  ];

  const shown = ordered
    .map((name) => map.get(name)!)
    .filter((section) => !hidden.includes(section.name));

  const lineCount =
    shown.reduce((total, section) => total + section.lines.length, 0) + 4;

  const overflow = lineCount > (template === "compact" ? 56 : 46);

  return (
    <section className="resume-preview-wrap" aria-label={t("shared.preview")}>
      <div className="preview-label">
        <strong>{t("shared.preview")}</strong>
        <span>
          {overflow ? t("shared.previewOverflow") : t("shared.previewOnePage")}
        </span>
      </div>

      {overflow && (
        <p className="warning" role="alert">
          {t("shared.overflowWarn", { n: lineCount })}
        </p>
      )}
      <article
        className={`resume-preview resume-preview-${template} resume-font-${appearance?.fontStyle || "default"} resume-density-${appearance?.density || "standard"} resume-accent-${appearance?.accent || "template"}`}
      >
        <h2>{displayName || t("shared.yourName")}</h2>
        {contactRows.map((row) => (
          <p className="preview-contact" key={row}>
            {row}
          </p>
        ))}

        {shown.map((section) => (
          <div className="preview-section" key={section.name}>
            {section.lines.map((line, index) =>
              index === 0 && section.name !== "Resume summary" ? (
                <h3 key={line}>{line.replace(/:$/, "")}</h3>
              ) : (
                <p
                  key={`${line}-${index}`}
                  className={
                    line.startsWith("-") || line.startsWith("•")
                      ? "preview-bullet"
                      : ""
                  }
                >
                  {line.replace(/^[-•]\s*/, "")}
                </p>
              ),
            )}
          </div>
        ))}
      </article>
    </section>
  );
}
