import {
  BedDouble, BarChart3, BookOpenCheck, ChefHat, ConciergeBell, LayoutDashboard, LogOut, Menu, Package, Receipt,
  Settings as SettingsIcon, Shirt, UtensilsCrossed, Wifi, WifiOff, X, type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { canSee, useAuth } from "../lib/auth";
import { shortDate } from "../lib/format";
import { useOnline } from "../lib/hooks";
import { useI18n } from "../lib/i18n";
import { queued, syncQueued } from "../lib/offline";
import BrandMark, { Watermark } from "./BrandMark";

export const NAV: { to: string; label: string; roles: string[]; icon: LucideIcon }[] = [
  { to: "/", label: "Dashboard", roles: [], icon: LayoutDashboard },
  { to: "/front-desk", label: "Front desk", roles: ["front_desk", "cashier"], icon: ConciergeBell },
  { to: "/reservations", label: "Reservations", roles: ["front_desk", "sales", "revenue"], icon: BookOpenCheck },
  { to: "/rooms", label: "Housekeeping", roles: ["housekeeping", "front_desk"], icon: BedDouble },
  { to: "/folios", label: "Billing", roles: ["front_desk", "cashier"], icon: Receipt },
  { to: "/pos", label: "POS", roles: ["waiter", "cashier"], icon: UtensilsCrossed },
  { to: "/kitchen", label: "Kitchen", roles: ["waiter"], icon: ChefHat },
  { to: "/laundry", label: "Laundry", roles: ["laundry", "front_desk", "housekeeping"], icon: Shirt },
  { to: "/inventory", label: "Inventory", roles: ["store_keeper"], icon: Package },
  { to: "/reports", label: "Reports", roles: [], icon: BarChart3 },
  { to: "/settings", label: "Settings", roles: ["revenue", "cashier"], icon: SettingsIcon },
];

export function homeFor(role: string, isManager: boolean) {
  if (isManager) return "/";
  return NAV.find((n) => n.roles.includes(role))?.to ?? "/";
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const online = useOnline();
  const navigate = useNavigate();
  const [calendar, setCalendar] = useState<{ ethiopian: string; ethiopian_am: string } | null>(null);
  const [businessDate, setBusinessDate] = useState<string | null>(null);
  const [pending, setPending] = useState(queued().length);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const lastPath = useRef(location.pathname);

  // Move focus to the page after navigation so screen readers announce the new screen.
  // Comparing paths (not a first-render flag) keeps this correct when effects re-run.
  useEffect(() => {
    setMenuOpen(false);
    if (lastPath.current === location.pathname) return;
    lastPath.current = location.pathname;
    mainRef.current?.focus({ preventScroll: true });
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  useEffect(() => {
    api("/calendar/today/").then(setCalendar).catch(() => {});
    api("/settings/").then((s) => setBusinessDate(s.business_date)).catch(() => {});
  }, []);

  useEffect(() => {
    const tick = () => setPending(queued().length);
    const id = window.setInterval(tick, 3000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (online && queued().length) syncQueued().then(() => setPending(queued().length)).catch(() => {});
  }, [online]);

  const items = NAV.filter((n) => (n.roles.length === 0 ? user?.is_manager : canSee(user, n.roles)));

  return (
    <div className="shell">
      <a className="skip-link" href="#main">Skip to main content</a>
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} aria-hidden="true" />}
      <aside id="sidebar" className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Main navigation">
        <div className="brand">
          <BrandMark className="brand-small" />
          <small>Hotel Management</small>
        </div>
        <nav>
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}>
              <n.icon size={19} strokeWidth={1.75} aria-hidden="true" />
              <span>{t(n.label)}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="who">
            {user?.first_name || user?.username}
            <small>{user?.role.replace(/_/g, " ")}</small>
          </div>
          <div className="lang">
            <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>EN</button>
            <button className={lang === "am" ? "active" : ""} onClick={() => setLang("am")}>አማ</button>
          </div>
          <button
            className="ghost signout"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOut size={18} strokeWidth={1.75} aria-hidden="true" />
            {t("Log out")}
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setMenuOpen(!menuOpen)} aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen} aria-controls="sidebar">
            {menuOpen ? <X size={22} aria-hidden="true" /> : <Menu size={22} aria-hidden="true" />}
          </button>
          <div className="dates">
            {businessDate && (
              <span>
                {t("Business date")}: <strong>{shortDate(businessDate)}</strong>
              </span>
            )}
            {calendar && <span className="eth">{lang === "am" ? calendar.ethiopian_am : calendar.ethiopian}</span>}
          </div>
          <span className={`net ${online ? "on" : "off"}`}>
            {online ? <Wifi size={14} aria-hidden="true" /> : <WifiOff size={14} aria-hidden="true" />}
            {online ? t("Online") : t("Offline")}
            {pending > 0 && ` · ${pending} queued`}
          </span>
        </header>
        <main className="content" id="main" ref={mainRef} tabIndex={-1}>
          <Watermark />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
