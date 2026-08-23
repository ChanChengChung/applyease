import {
  FormEvent,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { CVUploader } from "../../components/CVUploader";
import { ExperienceCard } from "../../components/ExperienceCard";
import {
  bulkConfirmExperiences,
  createExperience,
  deleteExperience,
  getExperienceImpacts,
  listExperiences,
  updateExperience,
  uploadCV,
} from "../../services/profileApi";
import type {
  Experience,
  ExperienceCategory,
  ExperienceImpact,
} from "../../types/experience";
import { useT } from "../../i18n/LanguageProvider";
import personalFolder from "../../assets/experience-folders/personal.png";
import educationFolder from "../../assets/experience-folders/education.png";
import internshipFolder from "../../assets/experience-folders/internship.png";
import leadershipFolder from "../../assets/experience-folders/leadership.png";
import researchFolder from "../../assets/experience-folders/research.png";
import projectFolder from "../../assets/experience-folders/project.png";

const PAGE_SIZE = 50;

const EXPERIENCE_FOLDERS: Array<{
  category: ExperienceCategory;
  icon: string;
  art: string;
}> = [
  { category: "personal", icon: "◉", art: personalFolder },
  { category: "education", icon: "⌑", art: educationFolder },
  { category: "internship", icon: "↗", art: internshipFolder },
  { category: "leadership", icon: "✦", art: leadershipFolder },
  { category: "research", icon: "⌕", art: researchFolder },
  { category: "project", icon: "◈", art: projectFolder },
];

export function ProfilePage({
  onExploreOpportunities,
  onReturnWelcome,
}: {
  onExploreOpportunities?: () => void;
  onReturnWelcome?: () => void;
}) {
  const [items, setItems] = useState<Experience[]>([]);
  const [impacts, setImpacts] = useState<Record<number, ExperienceImpact>>({});

  const [status, setStatus] = useState("");

  const [busy, setBusy] = useState(false);

  const [searchInput, setSearchInput] = useState("");

  const [query, setQuery] = useState("");

  const [filter, setFilter] = useState<"all" | "confirmed" | "pending">("all");

  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const [hasMore, setHasMore] = useState(false);

  const [showCreate, setShowCreate] = useState(false);

  const manualFormRef = useRef<HTMLFormElement>(null);

  const [openCategory, setOpenCategory] = useState<ExperienceCategory | null>(
    null,
  );

  const [newExperience, setNewExperience] = useState({
    title: "",
    organization: "",
    description: "",
    skills: "",
    source_file: "",
    category: "project" as ExperienceCategory,
  });
  const [personalDetails, setPersonalDetails] = useState({
    name: "",
    email: "",
    phone: "",
    location: "",
    address: "",
    linkedin: "",
    github: "",
  });

  const t = useT();

  const load = async (
    append = false,
    nextQuery = query,
    nextFilter = filter,
  ) => {
    try {
      const loaded = await listExperiences({
        query: nextQuery,
        confirmed:
          nextFilter === "all" ? undefined : nextFilter === "confirmed",
        limit: PAGE_SIZE,
        offset: append ? items.length : 0,
      });

      setItems((previous) => (append ? [...previous, ...loaded] : loaded));

      if (!append) {
        try {
          const impactRows = await getExperienceImpacts();
          setImpacts(
            Object.fromEntries(
              impactRows.map((item) => [item.experience_id, item]),
            ),
          );
        } catch {
          setImpacts({});
        }
      }

      setHasMore(loaded.length === PAGE_SIZE);

      return loaded;
    } catch {
      setStatus(t("profile.backendError"));

      return [];
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleUpload = async (file: File) => {
    setBusy(true);
    setStatus(t("profile.parsing"));
    try {
      const result = await uploadCV(file);
      setStatus(
        result.restored
          ? t("profile.reparsed")
          : result.reused
            ? t("profile.reused")
            : t("profile.parsed"),
      );
      await load();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : t("profile.parsed"));
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async (item: Experience) => {
    try {
      await updateExperience(item);
      setStatus(t("profile.saved"));
      await load();
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : t("profile.updateFailed"),
      );
      throw error;
    }
  };

  const handleDelete = async (item: Experience) => {
    if (!window.confirm(t("profile.deleteConfirm", { title: item.title })))
      return;
    try {
      await deleteExperience(item.id);
      setSelectedIds((current) => current.filter((id) => id !== item.id));
      setStatus(t("profile.deleted"));
      await load();
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : t("profile.deleteFailed"),
      );
    }
  };

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    const next = searchInput.trim();
    setQuery(next);
    void load(false, next, filter);
  };

  const changeFilter = (value: "all" | "confirmed" | "pending") => {
    setFilter(value);
    void load(false, query, value);
  };

  const toggleSelected = (id: number, selected: boolean) =>
    setSelectedIds((previous) =>
      selected
        ? [...new Set([...previous, id])]
        : previous.filter((item) => item !== id),
    );

  const confirmSelected = async () => {
    if (!selectedIds.length) return;
    setBusy(true);
    try {
      const result = await bulkConfirmExperiences(selectedIds);
      setStatus(t("profile.bulkConfirmed", { n: result.updated }));
      await load();
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : t("profile.bulkFailed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const submitCreate = async (event: FormEvent) => {
    event.preventDefault();

    if (
      newExperience.category === "personal"
        ? !personalDetails.name.trim()
        : !newExperience.title.trim()
    )
      return;

    setBusy(true);

    try {
      const isPersonal = newExperience.category === "personal";
      const personalDescription = [
        personalDetails.name && `${t("builder.name")}: ${personalDetails.name}`,
        personalDetails.email &&
          `${t("builder.email")}: ${personalDetails.email}`,
        personalDetails.phone &&
          `${t("builder.phone")}: ${personalDetails.phone}`,
        personalDetails.location &&
          `${t("builder.location")}: ${personalDetails.location}`,
        personalDetails.address &&
          `${t("profile.personal.address")}: ${personalDetails.address}`,
        personalDetails.linkedin && `LinkedIn: ${personalDetails.linkedin}`,
        personalDetails.github && `GitHub: ${personalDetails.github}`,
      ]
        .filter(Boolean)
        .join("\n");
      await createExperience({
        title: isPersonal
          ? personalDetails.name.trim() || t("profile.personal.defaultTitle")
          : newExperience.title.trim(),
        organization: isPersonal
          ? t("profile.personal.organization")
          : newExperience.organization.trim(),
        description: isPersonal
          ? personalDescription
          : newExperience.description.trim(),
        skills: [
          ...new Set(
            (isPersonal ? "" : newExperience.skills)
              .split(/[,，\n]/)
              .map((value) => value.trim())
              .filter(Boolean),
          ),
        ],
        achievements: [],
        source_file: newExperience.source_file.trim(),
        category: newExperience.category,
        confirmed: false,
      });

      setNewExperience({
        title: "",
        organization: "",
        description: "",
        skills: "",
        source_file: "",
        category: "project",
      });
      setPersonalDetails({
        name: "",
        email: "",
        phone: "",
        location: "",
        address: "",
        linkedin: "",
        github: "",
      });
      setShowCreate(false);
      setStatus(t("profile.created"));
      await load();
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : t("profile.createFailed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const openManualEntry = () => {
    setShowCreate(true);
    window.requestAnimationFrame(() => {
      const form = manualFormRef.current;
      if (typeof form?.scrollIntoView === "function") {
        form.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  };

  return (
    <main className="product-page experience-page">
      <header className="product-hero">
        <div>
          {onReturnWelcome && (
            <button
              type="button"
              className="experience-return-welcome"
              onClick={onReturnWelcome}
            >
              <span aria-hidden="true">←</span>
              {t("starter.changeMode")}
            </button>
          )}
          <p className="eyebrow">
            <strong>APPLYEASE</strong>
            <span className="page-wordmark">· EXPERIENCE BANK</span>
          </p>
          <h1>{t("profile.hero.title")}</h1>
          <p className="sub">{t("profile.hero.sub")}</p>
          <div
            className="experience-intake"
            aria-label={t("profile.intakeLabel")}
          >
            <div className="experience-intake-copy">
              <span aria-hidden="true">01</span>
              <div>
                <strong>{t("profile.intakeTitle")}</strong>
                <small>{t("profile.intakeSub")}</small>
              </div>
            </div>
            <div className="experience-intake-actions">
              <CVUploader
                onUpload={handleUpload}
                disabled={busy}
                label={t("profile.uploadCvCta")}
              />
              <button
                type="button"
                className="experience-manual-cta"
                aria-controls="manual-experience-form"
                onClick={openManualEntry}
              >
                <span aria-hidden="true">✦</span>
                {t("profile.addManual")}
              </button>
            </div>
          </div>
          <p className="status" role="status">
            {busy ? t("profile.parsing") : status}
          </p>
        </div>
        <div className="hero-orb hero-orb-experience" aria-hidden="true">
          <span>✦</span>
        </div>
      </header>
      <section className="product-content">
        <div className="section-heading">
          <div>
            <p className="section-kicker">01 · EVIDENCE LIBRARY</p>
            <h2>
              {t("profile.libraryTitle", {
                n: items.length,
                more: hasMore ? "+" : "",
              })}
            </h2>
          </div>
        </div>
        <form className="experience-toolbar" onSubmit={submitSearch}>
          <label>
            {t("profile.searchExperience")}
            <input
              aria-label={t("profile.searchExperience")}
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder={t("profile.searchPlaceholder")}
            />
          </label>
          <label>
            {t("profile.filterStatus")}
            <select
              aria-label={t("profile.filterStatus")}
              value={filter}
              onChange={(event) =>
                changeFilter(event.target.value as typeof filter)
              }
            >
              <option value="all">{t("profile.filterAll")}</option>
              <option value="confirmed">{t("profile.filterConfirmed")}</option>
              <option value="pending">{t("profile.filterPending")}</option>
            </select>
          </label>
          <button type="submit">{t("profile.searchBtn")}</button>
          <button
            type="button"
            disabled={!selectedIds.length || busy}
            onClick={() => void confirmSelected()}
          >
            {t("profile.confirmSelected", { n: selectedIds.length })}
          </button>
        </form>

        {showCreate && (
          <form
            id="manual-experience-form"
            ref={manualFormRef}
            className="card structured-form-card create-form"
            onSubmit={submitCreate}
          >
            <div className="form-card-header">
              <span className="form-card-icon" aria-hidden="true">
                ✦
              </span>
              <div>
                <p className="section-kicker">MANUAL EVIDENCE</p>
                <h3>{t("profile.newExperience")}</h3>
                <p>{t("profile.newExperienceSub")}</p>
              </div>
            </div>
            <div className="form-guidance" role="note">
              <span aria-hidden="true">↗</span>
              <p>{t("profile.experienceGuidance")}</p>
            </div>
            <div className="experience-form-grid">
              <label className="form-field form-field-wide">
                <span>{t("profile.field.category")}</span>
                <select
                  aria-label={t("profile.field.category")}
                  value={newExperience.category}
                  onChange={(event) =>
                    setNewExperience({
                      ...newExperience,
                      category: event.target.value as ExperienceCategory,
                    })
                  }
                >
                  {EXPERIENCE_FOLDERS.map((folder) => (
                    <option key={folder.category} value={folder.category}>
                      {t(`profile.category.${folder.category}`)}
                    </option>
                  ))}
                </select>
                <small>{t("profile.hint.category")}</small>
              </label>
              {newExperience.category === "personal" ? (
                <>
                  <div
                    className="personal-profile-intro form-field-wide"
                    role="note"
                  >
                    <strong>{t("profile.personal.title")}</strong>
                    <p>{t("profile.personal.sub")}</p>
                  </div>
                  <label className="form-field">
                    <span>
                      {t("builder.name")} <em>{t("shared.required")}</em>
                    </span>
                    <input
                      required
                      maxLength={100}
                      value={personalDetails.name}
                      placeholder={t("builder.namePlaceholder")}
                      onChange={(event) =>
                        setPersonalDetails({
                          ...personalDetails,
                          name: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="form-field">
                    <span>{t("builder.email")}</span>
                    <input
                      type="email"
                      maxLength={320}
                      value={personalDetails.email}
                      placeholder={t("builder.emailPlaceholder")}
                      onChange={(event) =>
                        setPersonalDetails({
                          ...personalDetails,
                          email: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="form-field">
                    <span>{t("builder.phone")}</span>
                    <input
                      type="tel"
                      maxLength={80}
                      value={personalDetails.phone}
                      placeholder={t("builder.phonePlaceholder")}
                      onChange={(event) =>
                        setPersonalDetails({
                          ...personalDetails,
                          phone: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="form-field">
                    <span>{t("builder.location")}</span>
                    <input
                      maxLength={160}
                      value={personalDetails.location}
                      placeholder={t("builder.locationPlaceholder")}
                      onChange={(event) =>
                        setPersonalDetails({
                          ...personalDetails,
                          location: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="form-field">
                    <span>{t("profile.personal.address")}</span>
                    <input
                      maxLength={240}
                      value={personalDetails.address}
                      placeholder={t("profile.personal.addressPlaceholder")}
                      onChange={(event) =>
                        setPersonalDetails({
                          ...personalDetails,
                          address: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="form-field">
                    <span>{t("builder.linkedin")}</span>
                    <input
                      type="url"
                      maxLength={500}
                      value={personalDetails.linkedin}
                      placeholder={t("builder.linkedinPlaceholder")}
                      onChange={(event) =>
                        setPersonalDetails({
                          ...personalDetails,
                          linkedin: event.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="form-field">
                    <span>{t("builder.github")}</span>
                    <input
                      type="url"
                      maxLength={500}
                      value={personalDetails.github}
                      placeholder={t("builder.githubPlaceholder")}
                      onChange={(event) =>
                        setPersonalDetails({
                          ...personalDetails,
                          github: event.target.value,
                        })
                      }
                    />
                  </label>
                </>
              ) : (
                <>
                  <label className="form-field">
                    <span>
                      {t("profile.field.title")} <em>{t("shared.required")}</em>
                    </span>
                    <input
                      aria-label={t("profile.field.title")}
                      required
                      maxLength={200}
                      placeholder={t("profile.placeholder.title")}
                      value={newExperience.title}
                      onChange={(event) =>
                        setNewExperience({
                          ...newExperience,
                          title: event.target.value,
                        })
                      }
                    />
                    <small>{t("profile.hint.title")}</small>
                  </label>
                  <label className="form-field">
                    <span>{t("profile.field.org")}</span>
                    <input
                      aria-label={t("profile.field.org")}
                      maxLength={200}
                      placeholder={t("profile.placeholder.org")}
                      value={newExperience.organization}
                      onChange={(event) =>
                        setNewExperience({
                          ...newExperience,
                          organization: event.target.value,
                        })
                      }
                    />
                    <small>{t("profile.hint.org")}</small>
                  </label>
                  <label className="form-field form-field-wide">
                    <span>{t("profile.field.desc")}</span>
                    <textarea
                      aria-label={t("profile.field.desc")}
                      maxLength={10000}
                      placeholder={t("profile.placeholder.desc")}
                      value={newExperience.description}
                      onChange={(event) =>
                        setNewExperience({
                          ...newExperience,
                          description: event.target.value,
                        })
                      }
                    />
                    <small>{t("profile.hint.desc")}</small>
                  </label>
                  <label className="form-field">
                    <span>{t("profile.field.skills")}</span>
                    <input
                      aria-label={t("profile.field.skills")}
                      placeholder={t("profile.placeholder.skills")}
                      value={newExperience.skills}
                      onChange={(event) =>
                        setNewExperience({
                          ...newExperience,
                          skills: event.target.value,
                        })
                      }
                    />
                    <small>{t("profile.hint.skills")}</small>
                  </label>
                  <label className="form-field">
                    <span>{t("profile.field.source")}</span>
                    <input
                      aria-label={t("profile.field.source")}
                      placeholder={t("profile.placeholder.source")}
                      value={newExperience.source_file}
                      onChange={(event) =>
                        setNewExperience({
                          ...newExperience,
                          source_file: event.target.value,
                        })
                      }
                    />
                    <small>{t("profile.hint.source")}</small>
                  </label>
                </>
              )}
            </div>
            <footer className="form-card-footer">
              <span>{t("profile.manualEvidenceNote")}</span>
              <div className="form-card-actions">
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() => setShowCreate(false)}
                >
                  {t("profile.cancelAdd")}
                </button>
                <button
                  disabled={
                    busy ||
                    (newExperience.category === "personal"
                      ? !personalDetails.name.trim()
                      : !newExperience.title.trim())
                  }
                >
                  {busy ? t("profile.saving") : t("profile.saveExperience")}
                </button>
              </div>
            </footer>
          </form>
        )}

        {items.length === 0 ? (
          <div className="empty">{t("profile.empty")}</div>
        ) : openCategory === null ? (
          <section
            className="experience-library-folders"
            aria-label={t("profile.folder.aria")}
          >
            <div className="experience-folder-grid">
              {EXPERIENCE_FOLDERS.map((folder) => {
                const folderItems = items.filter(
                  (item) => item.category === folder.category,
                );
                const count = folderItems.length;
                const pendingCount = folderItems.filter(
                  (item) => !item.confirmed,
                ).length;
                return (
                  <button
                    key={folder.category}
                    type="button"
                    className={`experience-folder folder-${folder.category}`}
                    style={
                      { "--folder-art": `url(${folder.art})` } as CSSProperties
                    }
                    onClick={() => setOpenCategory(folder.category)}
                    aria-label={t("profile.folder.openAria", {
                      category: t(`profile.category.${folder.category}`),
                      n: count,
                    })}
                  >
                    <span
                      className="experience-folder-tab"
                      aria-hidden="true"
                    />
                    <span className="experience-folder-icon" aria-hidden="true">
                      {folder.icon}
                    </span>
                    <span className="experience-folder-copy">
                      <strong>
                        {t(`profile.category.${folder.category}`)}
                      </strong>
                      <small>{t("profile.folder.count", { n: count })}</small>
                      {pendingCount > 0 && (
                        <span className="experience-folder-pending">
                          {t("profile.folder.pending", { n: pendingCount })}
                        </span>
                      )}
                    </span>
                    <span className="experience-folder-open" aria-hidden="true">
                      →
                    </span>
                  </button>
                );
              })}
            </div>
          </section>
        ) : (
          <section className="experience-category-view">
            <div className="experience-category-heading">
              <button
                type="button"
                className="folder-back-button"
                onClick={() => setOpenCategory(null)}
              >
                <span aria-hidden="true">←</span>
                {t("profile.folder.back")}
              </button>
              <div>
                <p className="section-kicker">
                  {t("profile.folder.categoryKicker")}
                </p>
                <h3>{t(`profile.category.${openCategory}`)}</h3>
                <p>
                  {t("profile.folder.categorySub", {
                    category: t(`profile.category.${openCategory}`),
                  })}
                </p>
              </div>
            </div>
            {items.some((item) => item.category === openCategory) ? (
              <div className="category-experience-grid">
                {items
                  .filter((item) => item.category === openCategory)
                  .map((item) => (
                    <ExperienceCard
                      key={item.id}
                      item={item}
                      onSave={handleSave}
                      onDelete={handleDelete}
                      selected={selectedIds.includes(item.id)}
                      onSelect={(selected) => toggleSelected(item.id, selected)}
                      impact={impacts[item.id]}
                      onExploreOpportunities={onExploreOpportunities}
                    />
                  ))}
              </div>
            ) : (
              <div className="empty category-empty">
                {t("profile.folder.empty", {
                  category: t(`profile.category.${openCategory}`),
                })}
              </div>
            )}
          </section>
        )}

        {hasMore && (
          <button
            className="load-more"
            disabled={busy}
            onClick={() => void load(true)}
          >
            {t("profile.searchBtn")}
          </button>
        )}
      </section>
    </main>
  );
}
