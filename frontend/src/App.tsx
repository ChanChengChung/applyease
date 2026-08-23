import { lazy, Suspense, useEffect, useState, type ReactElement } from "react";
import type { NavigationJob, PageId } from "./types/dashboard";
import {
  checkSession,
  installAuthInterceptor,
  logout,
} from "./services/authApi";
import type { AuthUser } from "./services/authApi";
import { Sidebar } from "./components/Sidebar";
import { AdvisorAssistant } from "./components/AdvisorAssistant";
import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { useT } from "./i18n/LanguageProvider";

// Keep the initial application shell small. Each workspace is fetched only
// when the user opens it; the dashboard remains the default first route.
const ApplicationBuilderPage = lazy(() =>
  import("./pages/ApplicationBuilder/ApplicationBuilderPage").then(
    (module) => ({ default: module.ApplicationBuilderPage }),
  ),
);
const ApplicationFormPage = lazy(() =>
  import("./pages/ApplicationForm/ApplicationFormPage").then((module) => ({
    default: module.ApplicationFormPage,
  })),
);
const DashboardPage = lazy(() =>
  import("./pages/Dashboard/DashboardPage").then((module) => ({
    default: module.DashboardPage,
  })),
);
const JobAnalysisPage = lazy(() =>
  import("./pages/JobAnalysis/JobAnalysisPage").then((module) => ({
    default: module.JobAnalysisPage,
  })),
);
const OpportunityRadarPage = lazy(() =>
  import("./pages/OpportunityRadar/OpportunityRadarPage").then((module) => ({
    default: module.OpportunityRadarPage,
  })),
);
const ProfilePage = lazy(() =>
  import("./pages/Profile/ProfilePage").then((module) => ({
    default: module.ProfilePage,
  })),
);
const WelcomePage = lazy(() =>
  import("./pages/Welcome/WelcomePage").then((module) => ({
    default: module.WelcomePage,
  })),
);
const ResourcePlanPage = lazy(() =>
  import("./pages/ResourcePlan/ResourcePlanPage").then((module) => ({
    default: module.ResourcePlanPage,
  })),
);
const TrackerPage = lazy(() =>
  import("./pages/Tracker/TrackerPage").then((module) => ({
    default: module.TrackerPage,
  })),
);
const AuthPage = lazy(() =>
  import("./pages/Auth/AuthPage").then((module) => ({
    default: module.AuthPage,
  })),
);
const AIQualityPage = lazy(() =>
  import("./pages/AIQuality/AIQualityPage").then((module) => ({
    default: module.AIQualityPage,
  })),
);
const SecurityPage = lazy(() =>
  import("./pages/Security/SecurityPage").then((module) => ({
    default: module.SecurityPage,
  })),
);

function PageLoading() {
  return (
    <main>
      <section
        className="card dashboard-state"
        role="status"
        aria-live="polite"
      >
        Loading workspace…
      </section>
    </main>
  );
}

export function App() {
  const authRequired = import.meta.env.VITE_AUTH_REQUIRED === "true";

  const [authenticated, setAuthenticated] = useState(false);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);

  const [checkingSession, setCheckingSession] = useState(authRequired);

  const t = useT();
  const errorBoundaryProps = {
    title: t("app.routeErrorTitle"),
    message: t("app.routeErrorMessage"),
    reloadLabel: t("app.reload"),
  };

  // Install the global fetch interceptor (token refresh / 401 handling) inside
  // an effect rather than during render. Side effects that mutate window.fetch
  // must not run on every render — this effect runs once when auth is required.
  useEffect(() => {
    if (authRequired) installAuthInterceptor();
  }, [authRequired]);

  useEffect(() => {
    const expired = () => setAuthenticated(false);
    window.addEventListener("applyease:unauthorized", expired);
    return () => window.removeEventListener("applyease:unauthorized", expired);
  }, []);

  useEffect(() => {
    if (!authRequired) return;
    void checkSession()
      .then((user) => {
        setAuthUser(user);
        setAuthenticated(Boolean(user));
      })
      .catch(() => {
        setAuthUser(null);
        setAuthenticated(false);
      })
      .finally(() => setCheckingSession(false));
  }, [authRequired]);

  const [page, setPage] = useState<PageId>("welcome");

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [selectedJob, setSelectedJob] = useState<NavigationJob | undefined>();

  const [selectedTrackerId, setSelectedTrackerId] = useState<number | undefined>();

  const navigate = (target: PageId, job?: NavigationJob) => {
    if (job) setSelectedJob(job);
    setPage(target);
    window.scrollTo?.({ top: 0, behavior: "smooth" });
  };

  // Page registry: maps each PageId to its render function. This replaces the
  // previous long `page === "x" ? <A/> : page === "y" ? <B/> : ...` ternary chain,
  // keeping the dispatch readable and adding new pages in one place.
  const PAGE_REGISTRY: Record<PageId, () => ReactElement> = {
    welcome: () => (
      <WelcomePage
        onOpenExperienceBank={() => navigate("profile")}
        onOpenLearningPlan={() => navigate("resources")}
      />
    ),
    dashboard: () => (
      <DashboardPage
        initialJob={selectedJob}
        onNavigate={navigate}
        onJobLoaded={setSelectedJob}
      />
    ),
    profile: () => (
      <ProfilePage
        onExploreOpportunities={() => navigate("opportunities")}
        onReturnWelcome={() => navigate("welcome")}
      />
    ),
    jobs: () => (
      <JobAnalysisPage
        initialJob={selectedJob}
        onJobAnalyzed={setSelectedJob}
        onReturnToDashboard={() => navigate("dashboard")}
        onOpenResourcePlan={(job) => navigate("resources", job)}
      />
    ),
    opportunities: () => (
      <OpportunityRadarPage
        onJobTracked={(job, tracker) => {
          setSelectedJob(job);
          setSelectedTrackerId(tracker.id);
          navigate("tracker", job);
        }}
      />
    ),
    builder: () => (
      <ApplicationBuilderPage
        initialJobId={selectedJob?.id}
        onJobSelected={setSelectedJob}
        onReturnToDashboard={() => navigate("dashboard")}
        onOpenApplicationForm={(jobId) =>
          navigate("form", { id: jobId } as NavigationJob)
        }
      />
    ),
    form: () => (
      <ApplicationFormPage
        initialJobId={selectedJob?.id}
        onJobSelected={setSelectedJob}
        onReturnToDashboard={() => navigate("dashboard")}
      />
    ),
    resources: () => <ResourcePlanPage initialJobId={selectedJob?.id} />,
    tracker: () => (
      <TrackerPage
        initialJob={selectedJob}
        initialTrackerId={selectedTrackerId}
        onOpenJob={(job) => navigate("jobs", job)}
        onOpenBuilder={(job) => navigate("builder", job)}
        onOpenForm={(job) => navigate("form", job)}
        onOpenLearningPlan={(job) => navigate("resources", job)}
      />
    ),
    "ai-quality": () => <AIQualityPage />,
    security: () => <SecurityPage />,
  };

  if (checkingSession)
    return (
      <main>
        <section className="card dashboard-state" aria-live="polite">
          {t("session.checking")}
        </section>
      </main>
    );

  if (authRequired && !authenticated)
    return (
      <AppErrorBoundary {...errorBoundaryProps}>
        <Suspense fallback={<PageLoading />}>
          <AuthPage
            onAuthenticated={() =>
              void checkSession().then((user) => {
                setAuthUser(user);
                setAuthenticated(Boolean(user));
              })
            }
          />
        </Suspense>
      </AppErrorBoundary>
    );

  return (
    <AppErrorBoundary {...errorBoundaryProps}>
      <div className="app-layout">
        <Sidebar
          activePage={page}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
          onNavigate={(id) => navigate(id)}
          authRequired={authRequired}
          currentUser={authUser}
          onLogout={
            authRequired
              ? () =>
                  void logout().finally(() => {
                    setAuthUser(null);
                    setAuthenticated(false);
                  })
              : undefined
          }
        />
        <div
          className={`app-main-scroll ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}
        >
          <main className="app-main">
            <div className="app-main-inner">
              {/* Dispatch to the active page via the registry above. */}
              <Suspense fallback={<PageLoading />}>
                {PAGE_REGISTRY[page]()}
              </Suspense>
            </div>
            <AdvisorAssistant activePage={page} activeJob={selectedJob} />
          </main>
        </div>
      </div>
    </AppErrorBoundary>
  );
}
