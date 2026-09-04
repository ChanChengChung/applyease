import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n/LanguageProvider";
import { useI18n } from "../i18n/LanguageProvider";
import { LANGUAGES } from "../i18n/index";
import type { PageId } from "../types/dashboard";
import type { AuthUser } from "../services/authApi";

export interface NavItem {
  id: PageId;
  labelKey: string;
  icon: React.ReactNode;
}

type NavGroup = {
  labelKey: string;
  items: NavItem[];
};

const ICON_PROPS = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const NAV_ITEMS: NavItem[] = [
  {
    id: "profile",
    labelKey: "nav.profile",
    icon: (
      <svg {...ICON_PROPS}>
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 21c.6-4 3-6 7-6s6.4 2 7 6" />
      </svg>
    ),
  },
  {
    id: "dashboard",
    labelKey: "nav.dashboard",
    icon: (
      <svg {...ICON_PROPS}>
        <rect x="3" y="3" width="7" height="9" rx="1.5" />
        <rect x="14" y="3" width="7" height="5" rx="1.5" />
        <rect x="14" y="12" width="7" height="9" rx="1.5" />
        <rect x="3" y="16" width="7" height="5" rx="1.5" />
      </svg>
    ),
  },
  {
    id: "opportunities",
    labelKey: "nav.opportunityHub",
    icon: (
      <svg {...ICON_PROPS}>
        <circle cx="11" cy="11" r="7" />
        <path d="M16.5 16.5 21 21" />
      </svg>
    ),
  },
  {
    id: "builder",
    labelKey: "nav.builder",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M6 3h9l3 3v15H6z" />
        <path d="M15 3v4h4M9 11h6M9 15h4" />
        <path d="m15.5 17.5 3.7-3.7 1.3 1.3-3.7 3.7-2 .7z" />
      </svg>
    ),
  },
  {
    id: "resources",
    labelKey: "nav.resources",
    icon: (
      <svg {...ICON_PROPS}>
        <path d="M5 4.5A2.5 2.5 0 0 1 7.5 2H19v17H7.5A2.5 2.5 0 0 0 5 21.5z" />
        <path d="M5 4.5A2.5 2.5 0 0 0 2.5 7V19.5A2.5 2.5 0 0 0 5 22" />
      </svg>
    ),
  },
  {
    id: "tracker",
    labelKey: "nav.tracker",
    icon: (
      <svg {...ICON_PROPS}>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M3 9h18M8 3v4M16 3v4" />
        <path d="M8.5 14l2 2 4-4" />
      </svg>
    ),
  },
];

const NAV_GROUPS: NavGroup[] = [
  { labelKey: "nav.foundation", items: [NAV_ITEMS[0]] },
  { labelKey: "nav.discovery", items: NAV_ITEMS.slice(2, 3) },
  { labelKey: "nav.prepare", items: NAV_ITEMS.slice(3, 5) },
  { labelKey: "nav.manage", items: NAV_ITEMS.slice(5) },
];

interface SidebarProps {
  activePage: PageId;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onNavigate: (id: PageId) => void;
  authRequired: boolean;
  onLogout?: () => void;
  currentUser?: AuthUser | null;
}

export function Sidebar({
  activePage,
  collapsed,
  onToggleCollapse,
  onNavigate,
  authRequired,
  onLogout,
  currentUser,
}: SidebarProps) {
  const t = useT();
  const { language, setLanguage } = useI18n();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);
  const accountRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);
  const [indicatorStyle, setIndicatorStyle] = useState<{
    top: number;
    height: number;
  }>({ top: 0, height: 0 });

  // Smooth indicator animation when active page changes
  useEffect(() => {
    if (activeRef.current && navRef.current) {
      const navRect = navRef.current.getBoundingClientRect();
      const btnRect = activeRef.current.getBoundingClientRect();
      setIndicatorStyle({
        top: btnRect.top - navRect.top,
        height: btnRect.height,
      });
    }
  }, [activePage]);

  // Close mobile sidebar on navigation
  const handleNavigate = (id: PageId) => {
    onNavigate(id);
    setMobileOpen(false);
    setAccountMenuOpen(false);
  };

  // Close mobile sidebar on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        mobileOpen &&
        navRef.current &&
        !navRef.current.contains(e.target as Node)
      ) {
        setMobileOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [mobileOpen]);

  useEffect(() => {
    if (!accountMenuOpen) return;

    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!accountRef.current?.contains(event.target as Node)) {
        setAccountMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, [accountMenuOpen]);

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <>
      {/* Mobile hamburger button */}
      <button
        className="sidebar-hamburger"
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label={t("nav.toggleMenu")}
        aria-expanded={mobileOpen}
      >
        <span />
        <span />
        <span />
      </button>

      {/* Mobile overlay */}
      <div
        className={`sidebar-overlay ${mobileOpen ? "open" : ""}`}
        onClick={() => setMobileOpen(false)}
        aria-hidden="true"
      />

      <aside
        ref={navRef}
        className={`sidebar ${collapsed ? "collapsed" : ""} ${
          mobileOpen ? "mobile-open" : ""
        }`}
        role="navigation"
        aria-label={t("nav.main")}
      >
        {/* Brand / Logo */}
        <div className="sidebar-brand">
          <button
            type="button"
            className="sidebar-brand-home"
            onClick={() => handleNavigate("welcome")}
            aria-label={t("nav.returnToWelcome")}
            title={t("nav.returnToWelcome")}
          >
            {!collapsed && (
              <>
                <span className="brand-text">
                  Apply<span className="brand-accent">Ease</span>
                </span>
                <span className="brand-home-caption">{t("nav.returnToWelcome")}</span>
              </>
            )}
            {collapsed && <span className="brand-icon">AE</span>}
          </button>
          <button
            className="sidebar-toggle"
            onClick={onToggleCollapse}
            aria-label={t("nav.toggle")}
            title={collapsed ? t("nav.expand") : t("nav.collapse")}
          >
            <svg
              className="sidebar-toggle-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {collapsed ? (
                <>
                  <polyline points="9 18 15 12 9 6" />
                </>
              ) : (
                <>
                  <polyline points="15 18 9 12 15 6" />
                </>
              )}
            </svg>
          </button>
        </div>

        {/* Scrollable nav area */}
        <nav className="sidebar-nav" aria-label={t("nav.pages")}>
          <p className="sidebar-journey-label">{t("nav.journey")}</p>
          {NAV_GROUPS.map((group) => (
            <section className="sidebar-nav-group" key={group.labelKey}>
              {!collapsed && <p>{t(group.labelKey)}</p>}
              <ul role="list">
                {group.items.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      ref={activePage === item.id ? activeRef : undefined}
                      className={`sidebar-link ${activePage === item.id ? "active" : ""}`}
                      onClick={() => handleNavigate(item.id)}
                      aria-current={activePage === item.id ? "page" : undefined}
                      title={t(item.labelKey)}
                    >
                      <span className="link-icon" aria-hidden="true">
                        {item.icon}
                      </span>
                      {!collapsed && (
                        <span className="link-label">{t(item.labelKey)}</span>
                      )}
                      {activePage === item.id && !collapsed && (
                        <span className="link-active-dot" aria-hidden="true" />
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </nav>

        {/* Sliding active indicator */}
        <div
          className="sidebar-indicator"
          style={{
            transform: `translateY(${indicatorStyle.top}px)`,
            height: `${indicatorStyle.height}px`,
            opacity: activePage ? 1 : 0,
          }}
          aria-hidden="true"
        />

        {/* Bottom section: language. Account actions include the personal workbench. */}
        <div className="sidebar-footer">
          <div
            ref={accountRef}
            className="sidebar-account-entry"
            onMouseEnter={() => setAccountMenuOpen(true)}
          >
            <button
              type="button"
              className="sidebar-link"
              onClick={() => setAccountMenuOpen(true)}
              aria-label={t("account.cardLabel")}
            >
              <span className="link-icon" aria-hidden="true">
                <svg {...ICON_PROPS}>
                  <circle cx="12" cy="8" r="3.25" />
                  <path d="M5.5 21c.7-3.9 3-5.8 6.5-5.8s5.8 1.9 6.5 5.8" />
                </svg>
              </span>
              {!collapsed && (
                <span className="link-label">{t("account.cardLabel")}</span>
              )}
            </button>
            {accountMenuOpen && (
              <section
                className="sidebar-account-popover"
                role="menu"
                aria-label={t("account.cardLabel")}
              >
                <div className="account-popover-profile">
                  <span className="account-avatar" aria-hidden="true">
                    {currentUser?.email?.slice(0, 1).toUpperCase() || "A"}
                  </span>
                  <span>
                    <strong>
                      {currentUser?.email || t(authRequired ? "account.signedIn" : "account.guest")}
                    </strong>
                    <small>
                      {!authRequired
                        ? t("account.guestSub")
                        : currentUser?.email_verified
                        ? t("account.verified")
                        : t("account.security")}
                    </small>
                  </span>
                </div>
                <button
                  type="button"
                  role="menuitem"
                  className="account-workbench"
                  onClick={() => handleNavigate("dashboard")}
                >
                  <span aria-hidden="true">▦</span>
                  {t("nav.dashboard")}
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="account-welcome"
                  onClick={() => handleNavigate("welcome")}
                >
                  <span aria-hidden="true">✦</span>
                  {t("nav.returnToWelcome")}
                </button>
                {authRequired && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => handleNavigate("security")}
                  >
                    {t("account.security")}
                  </button>
                )}
                <button
                  type="button"
                  role="menuitem"
                  className="account-ai-quality"
                  onClick={() => handleNavigate("ai-quality")}
                >
                  <span aria-hidden="true">✦</span>
                  {t("nav.aiQuality")}
                </button>
                {authRequired && onLogout && (
                  <button
                    type="button"
                    role="menuitem"
                    className="account-logout"
                    onClick={onLogout}
                  >
                    {t("nav.logout")}
                  </button>
                )}
              </section>
            )}
          </div>
          {/* Language switcher */}
          <div
            className="sidebar-lang"
            role="group"
            aria-label={t("nav.language")}
          >
            {LANGUAGES.map((item) => (
              <button
                key={item.code}
                type="button"
                className={`lang-btn ${language === item.code ? "active" : ""}`}
                aria-pressed={language === item.code}
                onClick={() => setLanguage(item.code)}
                title={item.label}
              >
                {/* When collapsed, show the 2-letter code (e.g. ZH/EN/TW) directly.
                    Codes are already 2 chars, so no truncation/slicing needed. */}
                {collapsed ? item.code.toUpperCase() : item.label}
              </button>
            ))}
          </div>
        </div>
      </aside>
    </>
  );
}
