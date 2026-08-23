import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { PageFeedback } from "../../components/PageFeedback";
import {
  createTracked,
  deleteTracked,
  downloadTrackerCalendar,
  getTrackerReminders,
  getTrackerSummary,
  getApplicationWorkspace,
  listTracked,
  saveCalendarDownload,
  updateTracked,
} from "../../services/trackerApi";
import type { NavigationJob } from "../../types/dashboard";
import type {
  TrackedApplication,
  TrackerReminder,
  TrackerStatus,
  TrackerSummary,
  ApplicationWorkspace,
} from "../../types/tracker";
import { useT } from "../../i18n/LanguageProvider";
import { listJobs } from "../../services/jobApi";
import type { Job } from "../../types/job";

const statuses: TrackerStatus[] = [
  "saved",
  "applied",
  "assessment",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];
const emptyForm = {
  company: "",
  role: "",
  job_id: "",
  deadline: "",
  status: "saved" as TrackerStatus,
  interview_date: "",
  follow_up_at: "",
  notes: "",
};
type Props = {
  initialJob?: NavigationJob;
  initialTrackerId?: number;
  onOpenJob?: (job: NavigationJob) => void;
  onOpenBuilder?: (job: NavigationJob) => void;
  onOpenForm?: (job: NavigationJob) => void;
  onOpenLearningPlan?: (job: NavigationJob) => void;
};
type FormState = typeof emptyForm;

function toForm(
  item?: TrackedApplication,
  initialJob?: NavigationJob,
): FormState {
  if (!item)
    return {
      ...emptyForm,
      company: initialJob?.company || "",
      role: initialJob?.title || "",
      job_id: initialJob?.id ? String(initialJob.id) : "",
    };

  return {
    company: item.company,
    role: item.role,
    job_id: item.job_id ? String(item.job_id) : "",
    deadline: item.deadline || "",
    status: item.status,
    interview_date: item.interview_date || "",
    follow_up_at: item.follow_up_at || "",
    notes: item.notes || "",
  };
}

function payload(form: FormState) {
  return {
    company: form.company.trim(),
    role: form.role.trim(),
    ...(form.job_id ? { job_id: Number(form.job_id) } : {}),
    deadline: form.deadline || null,
    status: form.status,
    interview_date: form.interview_date || null,
    follow_up_at: form.follow_up_at || null,
    notes: form.notes.trim(),
  };
}

export function TrackerPage({
  initialJob,
  initialTrackerId,
  onOpenJob,
  onOpenBuilder,
  onOpenForm,
  onOpenLearningPlan,
}: Props) {
  const [items, setItems] = useState<TrackedApplication[]>([]);
  const [workspaceJobs, setWorkspaceJobs] = useState<Job[]>([]);
  const [createMode, setCreateMode] = useState<
    "manual" | "workspace" | null
  >(
    initialJob ? "workspace" : null,
  );

  const [summary, setSummary] = useState<TrackerSummary | null>(null);

  const [reminders, setReminders] = useState<TrackerReminder[]>([]);
  const [workspaces, setWorkspaces] = useState<
    Record<number, ApplicationWorkspace>
  >({});

  const [reminderDays, setReminderDays] = useState(14);

  const [form, setForm] = useState<FormState>(() =>
    toForm(undefined, initialJob),
  );

  const [editing, setEditing] = useState<number | null>(null);

  const [draft, setDraft] = useState<FormState>(emptyForm);

  const [statusFilter, setStatusFilter] = useState<TrackerStatus | "">("");
  const [recordView, setRecordView] = useState<"planning" | "applied">(
    "planning",
  );

  const [sort, setSort] = useState<"deadline" | "created_at" | "follow_up">(
    "deadline",
  );

  const [loading, setLoading] = useState(true);

  const [saving, setSaving] = useState(false);

  const [error, setError] = useState("");
  const [calendarMessage, setCalendarMessage] = useState("");

  useEffect(() => {
    if (!initialTrackerId || loading || !items.some((item) => item.id === initialTrackerId)) {
      return;
    }
    setRecordView("planning");
    const timer = window.setTimeout(() => {
      document
        .getElementById(`tracked-application-${initialTrackerId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [initialTrackerId, items, loading]);

  useEffect(() => {
    if (!calendarMessage) return;
    const timer = window.setTimeout(() => setCalendarMessage(""), 3200);
    return () => window.clearTimeout(timer);
  }, [calendarMessage]);

  const t = useT();
  const statusLabel = (status: TrackerStatus | string) =>
    t(`tracker.status.${status}`);
  const linkedJob = (item: TrackedApplication): NavigationJob | undefined =>
    item.job_id
      ? { id: item.job_id, company: item.company, title: item.role }
      : undefined;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const [records, stats, due] = await Promise.all([
        listTracked({ status: statusFilter || undefined, sort }),
        getTrackerSummary(),
        getTrackerReminders(reminderDays),
      ]);

      setItems(records);
      const work = await Promise.all(
        records.map(async (item) => {
          try {
            return [item.id, await getApplicationWorkspace(item.id)] as const;
          } catch {
            return null;
          }
        }),
      );
      setWorkspaces(
        Object.fromEntries(
          work.filter(
            (item): item is [number, ApplicationWorkspace] => item !== null,
          ),
        ),
      );
      setSummary(stats);
      setReminders(due);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("tracker.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [sort, statusFilter, reminderDays, t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let active = true;
    void listJobs()
      .then((jobs) => {
        if (active) setWorkspaceJobs(jobs);
      })
      .catch(() => {
        if (active) setWorkspaceJobs([]);
      });
    return () => {
      active = false;
    };
  }, []);

  // Dashboard role cards open the relevant tracked application, rather than
  // merely landing the user at the top of the tracker.
  useEffect(() => {
    if (!initialJob || loading) return;
    const record = items.find((item) => item.job_id === initialJob.id);
    if (!record) return;
    setRecordView(record.status === "saved" ? "planning" : "applied");
    const frame = window.requestAnimationFrame(() => {
      document
        .getElementById(`tracked-application-${record.id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [initialJob, items, loading]);

  const add = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");

    try {
      await createTracked(payload(form));
      setForm(toForm(undefined));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("tracker.createFailed"));
    } finally {
      setSaving(false);
    }
  };

  const save = async (id: number) => {
    setSaving(true);
    setError("");

    try {
      await updateTracked(id, payload(draft));
      setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("tracker.updateFailed"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item: TrackedApplication) => {
    if (!window.confirm(t("tracker.deleteConfirm", { company: item.company })))
      return;

    setError("");
    try {
      await deleteTracked(item.id);
      if (editing === item.id) setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("tracker.deleteFailed"));
    }
  };

  const downloadCalendar = async (item: TrackedApplication) => {
    setError("");
    setCalendarMessage("");
    try {
      const file = await downloadTrackerCalendar(item.id);
      saveCalendarDownload(file);
      setCalendarMessage(t("tracker.calendarDownloadComplete"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("tracker.calendarFailed"));
    }
  };

  const moveToAppliedFolder = async (item: TrackedApplication) => {
    setSaving(true);
    setError("");
    try {
      await updateTracked(item.id, { status: "applied" });
      await load();
      setRecordView("applied");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("tracker.updateFailed"));
    } finally {
      setSaving(false);
    }
  };

  const moveToPreparationFolder = async (item: TrackedApplication) => {
    if (
      !window.confirm(
        t("tracker.returnToPreparationConfirm", { company: item.company }),
      )
    ) {
      return;
    }
    setSaving(true);
    setError("");
    try {
      await updateTracked(item.id, { status: "saved" });
      await load();
      setRecordView("planning");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("tracker.updateFailed"));
    } finally {
      setSaving(false);
    }
  };

  const renderFields = (
    value: FormState,
    setValue: (next: FormState) => void,
    prefix: string,
  ) => (
    <div className="form-grid">
      <label>
        {prefix}
        {t("tracker.company")}
        <input
          aria-label={`${prefix}${t("tracker.company")}`}
          required
          value={value.company}
          onChange={(e) => setValue({ ...value, company: e.target.value })}
        />
      </label>
      <label>
        {prefix}
        {t("tracker.role")}
        <input
          aria-label={`${prefix}${t("tracker.role")}`}
          required
          value={value.role}
          onChange={(e) => setValue({ ...value, role: e.target.value })}
        />
      </label>
      <label>
        {prefix}
        {t("tracker.deadline")}
        <input
          aria-label={`${prefix}${t("tracker.deadline")}`}
          type="date"
          value={value.deadline}
          onChange={(e) => setValue({ ...value, deadline: e.target.value })}
        />
      </label>
      <label>
        {prefix}
        {t("tracker.status")}
        <select
          aria-label={`${prefix}${t("tracker.status")}`}
          value={value.status}
          onChange={(e) =>
            setValue({ ...value, status: e.target.value as TrackerStatus })
          }
        >
          {statuses.map((s) => (
            <option key={s} value={s}>
              {statusLabel(s)}
            </option>
          ))}
        </select>
      </label>
      <label>
        {prefix}
        {t("tracker.interview")}
        <input
          aria-label={`${prefix}${t("tracker.interview")}`}
          type="date"
          value={value.interview_date}
          onChange={(e) =>
            setValue({ ...value, interview_date: e.target.value })
          }
        />
      </label>
      <label>
        {prefix}
        {t("tracker.followUp")}
        <input
          aria-label={`${prefix}${t("tracker.followUp")}`}
          type="date"
          value={value.follow_up_at}
          onChange={(e) => setValue({ ...value, follow_up_at: e.target.value })}
        />
      </label>
    </div>
  );

  const appliedStatuses: TrackerStatus[] = [
    "applied",
    "assessment",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
  ];
  const displayedItems = items.filter((item) =>
    recordView === "applied"
      ? appliedStatuses.includes(item.status)
      : item.status === "saved",
  );
  const appliedCount = items.filter((item) =>
    appliedStatuses.includes(item.status),
  ).length;

  return (
    <main className="product-page tracker-page">
      <header className="product-hero">
        <div>
          <p className="eyebrow">
            <strong>APPLYEASE</strong>
            <span className="page-wordmark">· APPLICATION TRACKER</span>
          </p>
          <h1>{t("tracker.hero.title")}</h1>
          <p className="sub">{t("tracker.hero.sub")}</p>
        </div>
        <div className="hero-orb hero-orb-tracker" aria-hidden="true">
          <span>◷</span>
        </div>
      </header>
      <section className="product-content">
        {error && <PageFeedback kind="error" message={error} />}
        {calendarMessage && (
          <div className="app-toast app-toast-success" role="status">
            <span aria-hidden="true">✓</span>
            {calendarMessage}
          </div>
        )}

        {initialJob && (
          <section
            className="tracker-current-target"
            aria-label={t("tracker.currentTarget")}
          >
            <div className="tracker-current-target-mark" aria-hidden="true">
              ◉
            </div>
            <div>
              <p className="section-kicker">{t("tracker.currentTarget")}</p>
              <h2>
                {initialJob.company} · {initialJob.title}
              </h2>
              <p>{t("tracker.currentTargetHelp")}</p>
            </div>
            <button type="button" onClick={() => onOpenJob?.(initialJob)}>
              <span aria-hidden="true">⌕</span>
              {t("tracker.openRoleAnalysis")}
            </button>
          </section>
        )}

        {summary && (
          <section
            className="tracker-command"
            aria-label={t("tracker.statsLabel")}
          >
            <div className="tracker-command-copy">
              <p className="section-kicker">APPLICATION PULSE</p>
              <h2>{t("tracker.stats", { n: summary.total })}</h2>
            </div>
            <div className="tracker-stat-grid">
              <div>
                <span>{t("tracker.commandActive")}</span>
                <strong>{summary.active}</strong>
              </div>
              <div className={summary.overdue ? "attention" : ""}>
                <span>{t("tracker.commandDeadline")}</span>
                <strong>{summary.overdue}</strong>
              </div>
              <div>
                <span>{t("tracker.commandFollowup")}</span>
                <strong>{summary.follow_ups_due}</strong>
              </div>
            </div>
          </section>
        )}
        <section
          className="card tracker-reminders"
          aria-label={t("tracker.remindersLabel")}
        >
          <div className="card-header">
            <div>
              <h2>{t("tracker.remindersTitle")}</h2>
              <p>{t("tracker.remindersHelp")}</p>
            </div>
            <label>
              {t("tracker.reminderRange")}
              <select
                aria-label={t("tracker.reminderRange")}
                value={reminderDays}
                onChange={(e) => setReminderDays(Number(e.target.value))}
              >
                <option value="7">7 {t("tracker.days")}</option>
                <option value="14">14 {t("tracker.days")}</option>
                <option value="30">30 {t("tracker.days")}</option>
                <option value="90">90 {t("tracker.days")}</option>
              </select>
            </label>
          </div>
          {loading ? (
            <p>{t("tracker.remindersLoading")}</p>
          ) : reminders.length === 0 ? (
            <p>{t("tracker.remindersEmpty")}</p>
          ) : (
            <ul className="tracker-reminder-list">
              {reminders.map((reminder) => (
                <li key={`${reminder.application_id}-${reminder.kind}`}>
                  <strong>
                    {reminder.state === "overdue"
                      ? t("tracker.reminderOverdue")
                      : reminder.state === "today"
                        ? t("tracker.reminderToday")
                        : reminder.due_date}
                  </strong>{" "}
                  · {reminder.title}
                </li>
              ))}
            </ul>
          )}
        </section>
        <form
          className="card structured-form-card tracker-create-card"
          onSubmit={add}
        >
          <div className="form-card-header">
            <span className="form-card-icon" aria-hidden="true">
              ◷
            </span>
            <div>
              <p className="section-kicker">APPLICATION RECORD</p>
              <h2>{t("tracker.addTitle")}</h2>
              <p>{t("tracker.addHelp")}</p>
            </div>
          </div>
          <div className="tracker-create-mode" role="group" aria-label={t("tracker.addMethod")}>
            <button
              type="button"
              className={createMode === "manual" ? "active" : ""}
              onClick={() => {
                setCreateMode("manual");
                setForm(toForm(undefined));
              }}
            >
              {t("tracker.addManually")}
            </button>
            <button
              type="button"
              className={createMode === "workspace" ? "active" : ""}
              onClick={() => setCreateMode("workspace")}
            >
              {t("tracker.importWorkspace")}
            </button>
          </div>
          {createMode === "workspace" && (
            <label className="tracker-workspace-picker">
              {t("tracker.chooseWorkspaceRole")}
              <select
                aria-label={t("tracker.chooseWorkspaceRole")}
                value={form.job_id}
                onChange={(event) => {
                  const selected = workspaceJobs.find(
                    (job) => job.id === Number(event.target.value),
                  );
                  setForm(
                    selected
                      ? {
                          ...emptyForm,
                          job_id: String(selected.id),
                          company: selected.company,
                          role: selected.title,
                        }
                      : toForm(undefined),
                  );
                }}
              >
                <option value="">{t("tracker.chooseWorkspaceRolePlaceholder")}</option>
                {workspaceJobs
                  .filter(
                    (job) =>
                      !items.some((item) => item.job_id === job.id) ||
                      String(job.id) === form.job_id,
                  )
                  .map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.company} · {job.title}
                    </option>
                  ))}
              </select>
              <small>{t("tracker.importWorkspaceHelp")}</small>
            </label>
          )}
          {createMode && (
            <div className="tracker-create-fields">
              {renderFields(
                form,
                setForm,
                initialJob ? "" : t("tracker.prefixAdd"),
              )}
              <label className="form-field form-field-wide">
                {t("tracker.notes")}
                <textarea
                  placeholder={t("tracker.notesPlaceholder")}
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
              </label>
              <button disabled={saving || (createMode === "workspace" && !form.job_id)}>
                {saving ? t("tracker.saving") : t("tracker.add")}
              </button>
            </div>
          )}
        </form>
        <section
          className="tracker-records"
          aria-label={t("tracker.myApplications")}
        >
          <header className="tracker-records-header">
            <div>
              <p className="section-kicker">MY APPLICATIONS</p>
              <h2>{t("tracker.myApplications")}</h2>
            </div>
            <div className="tracker-filters">
              <label>
                {t("tracker.filterStatus")}
                <select
                  aria-label={t("tracker.filterStatus")}
                  value={statusFilter}
                  onChange={(e) =>
                    setStatusFilter(e.target.value as TrackerStatus | "")
                  }
                >
                  <option value="">{t("tracker.filterAll")}</option>
                  {statuses.map((s) => (
                    <option key={s} value={s}>
                      {statusLabel(s)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t("tracker.sort")}
                <select
                  aria-label={t("tracker.sort")}
                  value={sort}
                  onChange={(e) => setSort(e.target.value as typeof sort)}
                >
                  <option value="deadline">{t("tracker.sortDeadline")}</option>
                  <option value="follow_up">{t("tracker.sortFollow")}</option>
                  <option value="created_at">{t("tracker.sortCreated")}</option>
                </select>
              </label>
            </div>
          </header>

          <div className="tracker-folder-switch" role="group" aria-label={t("tracker.folderView")}>
            <button
              type="button"
              className={recordView === "planning" ? "active" : ""}
              onClick={() => setRecordView("planning")}
            >
              <span aria-hidden="true">◇</span>
              <strong>{t("tracker.planningFolder")}</strong>
              <small>{items.filter((item) => item.status === "saved").length}</small>
            </button>
            <button
              type="button"
              className={recordView === "applied" ? "active" : ""}
              onClick={() => setRecordView("applied")}
            >
              <span aria-hidden="true">▣</span>
              <strong>{t("tracker.appliedFolder")}</strong>
              <small>{appliedCount}</small>
            </button>
          </div>

          {loading ? (
            <PageFeedback kind="info" message={t("tracker.loading")} />
          ) : items.length === 0 ? (
            <PageFeedback kind="info" message={t("tracker.empty")} />
          ) : displayedItems.length === 0 ? (
            <PageFeedback
              kind="info"
              message={
                recordView === "applied"
                  ? t("tracker.appliedFolderEmpty")
                  : t("tracker.planningFolderEmpty")
              }
            />
          ) : (
            displayedItems.map((item) => (
              <article
                className={`card tracker-item tracker-application-card ${item.is_overdue ? "is-overdue" : ""} ${item.id === initialTrackerId ? "is-imported" : ""}`}
                key={item.id}
                id={`tracked-application-${item.id}`}
                tabIndex={-1}
              >
                {editing === item.id ? (
                  <>
                    <h2>{t("tracker.editTitle")}</h2>
                    {renderFields(draft, setDraft, t("tracker.prefixEdit"))}
                    <label>
                      {t("tracker.notes")}
                      <textarea
                        value={draft.notes}
                        onChange={(e) =>
                          setDraft({ ...draft, notes: e.target.value })
                        }
                      />
                    </label>
                    <button
                      disabled={saving}
                      onClick={() => void save(item.id)}
                    >
                      {t("tracker.save")}
                    </button>
                    <button type="button" onClick={() => setEditing(null)}>
                      {t("tracker.cancel")}
                    </button>
                  </>
                ) : (
                  <>
                    {item.id === initialTrackerId && (
                      <p className="tracker-imported-notice" role="status">
                        {t("tracker.importedFromRadar")}
                      </p>
                    )}
                    <div className="card-header tracker-item-header">
                      <div className="tracker-item-title">
                        <div
                          className="tracker-application-illustration"
                          aria-hidden="true"
                        >
                          <span>◷</span>
                          <i />
                          <b />
                        </div>
                        <div>
                          <h2>{item.company}</h2>
                          <span>{item.role}</span>
                        </div>
                      </div>
                      <div className="tracker-item-actions">
                        {item.status === "saved" && (
                          <button
                            type="button"
                            className="tracker-file-application"
                            disabled={saving}
                            onClick={() => void moveToAppliedFolder(item)}
                          >
                            {t("tracker.moveToAppliedFolder")}
                          </button>
                        )}
                        {item.status !== "saved" && (
                          <button
                            type="button"
                            className="tracker-file-application tracker-return-preparation"
                            disabled={saving}
                            onClick={() => void moveToPreparationFolder(item)}
                          >
                            {t("tracker.returnToPreparation")}
                          </button>
                        )}
                        <button
                          type="button"
                          className="tracker-calendar-action"
                          onClick={() => void downloadCalendar(item)}
                        >
                          {t("tracker.exportCalendar")}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditing(item.id);
                            setDraft(toForm(item));
                          }}
                        >
                          {t("tracker.edit")}
                        </button>
                        <button type="button" onClick={() => void remove(item)}>
                          {t("tracker.delete")}
                        </button>
                      </div>
                    </div>
                    <div className="tracker-date-rail">
                      <span className="status-badge">
                        <i aria-hidden="true" />
                        {statusLabel(item.status)}
                      </span>
                      {item.deadline && (
                        <span>
                          <small>{t("tracker.deadline")}</small>
                          {item.deadline}
                        </span>
                      )}
                      {item.interview_date && (
                        <span>
                          <small>{t("tracker.interview")}</small>
                          {item.interview_date}
                        </span>
                      )}
                      {item.follow_up_at && (
                        <span>
                          <small>{t("tracker.followUp")}</small>
                          {item.follow_up_at}
                        </span>
                      )}
                    </div>
                    {item.is_overdue && (
                      <p role="alert">{t("tracker.overdueAlert")}</p>
                    )}
                    {item.is_follow_up_due && (
                      <p role="alert">{t("tracker.followDue")}</p>
                    )}
                    {item.next_action && (
                      <p>
                        {t("tracker.nextAction", { action: item.next_action })}
                      </p>
                    )}
                    {item.notes && <p>{item.notes}</p>}
                    {workspaces[item.id] && (
                      <section
                        className="tracker-workspace"
                        aria-label="Application workspace"
                      >
                        {workspaces[item.id].job_id ? (
                          (() => {
                            const workspace = workspaces[item.id];
                            const score = workspace.match_score ?? 0;
                            return (
                              <>
                                <div className="tracker-workspace-header">
                                  <div>
                                    <strong>{t("tracker.workspace")}</strong>
                                    <p>{t("tracker.workspaceSummary")}</p>
                                  </div>
                                  <div
                                    className="match-ring"
                                    aria-label={t("tracker.workspaceMatch", {
                                      score,
                                    })}
                                    style={
                                      {
                                        "--match-score": `${Math.max(0, Math.min(100, score)) * 3.6}deg`,
                                      } as CSSProperties
                                    }
                                  >
                                    <span>
                                      {score}
                                      <small>/100</small>
                                    </span>
                                  </div>
                                </div>
                                <div className="workspace-overview">
                                  <div>
                                    <small>
                                      {t("tracker.workspaceEvidenceLabel")}
                                    </small>
                                    <strong>{workspace.evidence_count}</strong>
                                  </div>
                                  <div>
                                    <small>
                                      {t("tracker.workspaceMaterialsLabel")}
                                    </small>
                                    <strong>
                                      {workspace.material_types.join(" · ") ||
                                        "—"}
                                    </strong>
                                  </div>
                                  <div>
                                    <small>
                                      {t("tracker.workspaceAnswersLabel")}
                                    </small>
                                    <strong>
                                      {workspace.answers_ready}/
                                      {workspace.questions_total}
                                    </strong>
                                  </div>
                                  <div>
                                    <small>
                                      {t("tracker.workspaceLearningLabel")}
                                    </small>
                                    <strong>
                                      {workspace.learning_plan_id
                                        ? t("tracker.workspaceLearningReady", {
                                            steps:
                                              workspace.learning_plan_steps ||
                                              0,
                                          })
                                        : t("tracker.workspaceLearningEmpty")}
                                    </strong>
                                  </div>
                                </div>
                                {linkedJob(item) && (
                                  <div
                                    className="tracker-workspace-actions"
                                    aria-label={t("tracker.workspace")}
                                  >
                                    <button
                                      type="button"
                                      onClick={() =>
                                        onOpenJob?.(linkedJob(item)!)
                                      }
                                    >
                                      {t("tracker.openAnalysis")}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        onOpenBuilder?.(linkedJob(item)!)
                                      }
                                    >
                                      {t("tracker.openMaterials")}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        onOpenForm?.(linkedJob(item)!)
                                      }
                                    >
                                      {t("tracker.openAnswers")}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        onOpenLearningPlan?.(linkedJob(item)!)
                                      }
                                    >
                                      {t("tracker.openLearning")}
                                    </button>
                                  </div>
                                )}
                                {workspace.missing_skills.length > 0 && (
                                  <div className="workspace-gaps">
                                    <strong>
                                      {t("tracker.workspaceGapsTitle")}
                                    </strong>
                                    <div>
                                      {workspace.missing_skills
                                        .slice(0, 3)
                                        .map((skill) => (
                                          <span className="missing" key={skill}>
                                            {skill}
                                          </span>
                                        ))}
                                    </div>
                                  </div>
                                )}
                                {((workspace.material_versions || []).length > 0 ||
                                  workspace.questions_total > 0 ||
                                  Boolean(workspace.learning_plan_id)) && (
                                  <div className="materials-ready-panel">
                                    <div>
                                      <strong>
                                        {t("tracker.materialsReadyTitle")}
                                      </strong>
                                      <p>
                                        {t("tracker.materialsReadySub", {
                                          n: workspace.material_versions.length,
                                        })}
                                      </p>
                                    </div>
                                    <ul>
                                      {workspace.material_versions.map(
                                        (version) => (
                                          <li key={version.id}>
                                            <span>{version.material_type}</span>
                                            <small>
                                              {version.fact_check_passed
                                                ? t("tracker.integrityPass")
                                                : t("tracker.integrityReview")}
                                            </small>
                                          </li>
                                        ),
                                      )}
                                      <li className="tracker-prepared-answer">
                                        <span>{t("tracker.materialsReadyAnswers", {
                                          ready: workspace.answers_ready,
                                          total: workspace.questions_total,
                                        })}</span>
                                      </li>
                                      <li className="tracker-prepared-learning">
                                        <span>
                                          {workspace.learning_plan_id
                                            ? t("tracker.materialsReadyLearning", {
                                                steps: workspace.learning_plan_steps || 0,
                                              })
                                            : t("tracker.materialsReadyLearningEmpty")}
                                        </span>
                                      </li>
                                    </ul>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        linkedJob(item) &&
                                        onOpenBuilder?.(linkedJob(item)!)
                                      }
                                    >
                                      {t("tracker.openMaterials")}
                                    </button>
                                  </div>
                                )}
                              </>
                            );
                          })()
                        ) : (
                          <p>{t("tracker.workspaceUnlinked")}</p>
                        )}
                      </section>
                    )}
                  </>
                )}
              </article>
            ))
          )}
        </section>
      </section>
    </main>
  );
}
