import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { canSee, useAuth } from "../lib/auth";
import { shortDate } from "../lib/format";
import { useOnline } from "../lib/hooks";
import { useI18n } from "../lib/i18n";
import { queued, syncQueued } from "../lib/offline";

export const NAV = [
  { to: "/", label: "Dashboard", roles: [] as string[] },
  { to: "/front-desk", label: "Front desk", roles: ["front_desk", "cashier"] },
  { to: "/reservations", label: "Reservations", roles: ["front_desk", "sales", "revenue"] },
  { to: "/rooms", label: "Housekeeping", roles: ["housekeeping", "front_desk"] },
  { to: "/folios", label: "Billing", roles: ["front_desk", "cashier"] },
  { to: "/pos", label: "POS", roles: ["waiter", "cashier"] },
  { to: "/kitchen", label: "Kitchen", roles: ["waiter"] },
  { to: "/laundry", label: "Laundry", roles: ["laundry", "front_desk", "housekeeping"] },
  { to: "/inventory", label: "Inventory", roles: ["store_keeper"] },
  { to: "/reports", label: "Reports", roles: [] },
  { to: "/settings", label: "Settings", roles: ["revenue", "cashier"] },
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
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand">
          <span className="logo">V</span>
          <div>
            <strong>Vora Addis</strong>
            <small>Hotel Management</small>
          </div>
        </div>
        <nav onClick={() => setMenuOpen(false)}>
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}>
              {t(n.label)}
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
            className="ghost"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            {t("Log out")}
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="ghost menu-btn" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">☰</button>
          <div className="dates">
            {businessDate && (
              <span>
                {t("Business date")}: <strong>{shortDate(businessDate)}</strong>
              </span>
            )}
            {calendar && <span className="eth">{lang === "am" ? calendar.ethiopian_am : calendar.ethiopian}</span>}
          </div>
          <span className={`net ${online ? "on" : "off"}`}>
            {online ? t("Online") : t("Offline")}
            {pending > 0 && ` · ${pending} queued`}
          </span>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
