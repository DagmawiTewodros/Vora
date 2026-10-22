import { useEffect, useState } from "react";
import { ErrorBox, Field, Modal } from "../components/ui";
import { patch, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { birr, dateTime, money, shortDate } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

export default function Settings() {
  const { t } = useI18n();
  const { user } = useAuth();
  const tabs = [
    user?.is_manager && "Hotel",
    (user?.is_manager || user?.role === "cashier") && "Exchange rate",
    (user?.is_manager || user?.role === "revenue") && "Rates",
    (user?.is_manager || user?.role === "revenue") && "Channels",
    user?.is_manager && "Staff",
  ].filter(Boolean) as string[];
  const [tab, setTab] = useState(tabs[0]);
  return (
    <div className="page">
      <div className="page-head"><h1>{t("Settings")}</h1></div>
      <div className="tabs">{tabs.map((x) => <button key={x} className={tab === x ? "active" : ""} onClick={() => setTab(x)}>{x}</button>)}</div>
      {tab === "Hotel" && <HotelSettings />}
      {tab === "Exchange rate" && <ExchangeRates />}
      {tab === "Rates" && <RatePlans />}
      {tab === "Channels" && <Channels />}
      {tab === "Staff" && <StaffList />}
    </div>
  );
}

function HotelSettings() {
  const settings = useApi("/settings/");
  const [form, setForm] = useState<any>(null);
  const { busy, error, run } = useAction();
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (settings.data) setForm(settings.data); }, [settings.data]);
  if (!form) return null;
  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <div className="card stack">
      <div className="grid3">
        <Field label="Hotel name"><input value={form.name} onChange={set("name")} /></Field>
        <Field label="TIN"><input value={form.tin} onChange={set("tin")} /></Field>
        <Field label="VAT registration no."><input value={form.vat_registration_no} onChange={set("vat_registration_no")} /></Field>
        <Field label="Address"><input value={form.address} onChange={set("address")} /></Field>
        <Field label="Phone"><input value={form.phone} onChange={set("phone")} /></Field>
        <Field label="Email"><input value={form.email} onChange={set("email")} /></Field>
        <Field label="VAT rate (0.15 = 15%)"><input type="number" step="0.0001" value={form.vat_rate} onChange={set("vat_rate")} /></Field>
        <Field label="Service charge rate"><input type="number" step="0.0001" value={form.service_charge_rate} onChange={set("service_charge_rate")} /></Field>
        <Field label="Invoice prefix"><input value={form.invoice_prefix} onChange={set("invoice_prefix")} /></Field>
        <Field label="Business date"><input type="date" value={form.business_date ?? ""} onChange={set("business_date")} /></Field>
      </div>
      <label className="radio"><input type="checkbox" checked={form.vat_on_service_charge} onChange={set("vat_on_service_charge")} /> Charge VAT on the service charge too</label>
      <label className="radio"><input type="checkbox" checked={form.prices_include_tax} onChange={set("prices_include_tax")} /> Room rates and menu prices already include service charge and VAT</label>
      <label className="radio"><input type="checkbox" checked={form.show_ethiopian_date} onChange={set("show_ethiopian_date")} /> Show the Ethiopian date on invoices</label>
      <ErrorBox error={error} />
      <div><button className="primary" disabled={busy} onClick={() => run(async () => { await patch("/settings/1/", form); setSaved(true); })}>Save</button> {saved && <span className="muted">Saved</span>}</div>
    </div>
  );
}

function ExchangeRates() {
  const rates = useApi<any[]>("/exchange-rates/");
  const [rate, setRate] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const { busy, error, run } = useAction();
  return (
    <div className="card stack">
      <div className="grid3">
        <Field label="Date"><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <Field label="1 USD = ? ETB"><input type="number" step="0.0001" value={rate} onChange={(e) => setRate(e.target.value)} /></Field>
        <div className="field"><span>&nbsp;</span><button className="primary" disabled={busy || !rate} onClick={() => run(async () => { await post("/exchange-rates/", { date, usd_to_etb: rate }); setRate(""); rates.reload(); })}>Save rate</button></div>
      </div>
      <ErrorBox error={error} />
      <table>
        <thead><tr><th>Date</th><th>Ethiopian date</th><th>Rate</th><th>Entered by</th></tr></thead>
        <tbody>{(rates.data ?? []).slice(0, 30).map((r) => <tr key={r.id}><td>{shortDate(r.date)}</td><td>{r.ethiopian_date}</td><td>{r.usd_to_etb}</td><td>{r.entered_by_name}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function RatePlans() {
  const plans = useApi<any[]>("/rate-plans/");
  const types = useApi<any[]>("/room-types/");
  const [editing, setEditing] = useState<any | null>(null);
  const { busy, error, run } = useAction();
  const save = () => run(async () => {
    const body = { ...editing, season_start: editing.season_start || null, season_end: editing.season_end || null };
    if (editing.id) await patch(`/rate-plans/${editing.id}/`, body);
    else await post("/rate-plans/", body);
    setEditing(null);
    plans.reload();
  });
  const set = (k: string) => (e: any) => setEditing({ ...editing, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <div className="card">
      <div className="section-head"><h2>Rate plans</h2><button onClick={() => setEditing({ name: "", code: "", room_type: types.data?.[0]?.id, price_etb: "", price_usd: "", breakfast_included: true, is_public: true, is_active: true, priority: 0 })}>Add rate</button></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Room type</th><th>Plan</th><th>ETB</th><th>USD</th><th>Season</th><th>Breakfast</th><th>Public</th><th /></tr></thead>
          <tbody>
            {(plans.data ?? []).map((p) => (
              <tr key={p.id} className={p.is_active ? "" : "void"}>
                <td>{p.room_type_name}</td><td>{p.name} <small className="muted">{p.code}</small></td><td>{birr(p.price_etb)}</td><td>{money(p.price_usd, "USD")}</td>
                <td>{p.season_start ? `${shortDate(p.season_start)} – ${shortDate(p.season_end)}` : "All year"}</td>
                <td>{p.breakfast_included ? "Yes" : "No"}</td><td>{p.is_public ? "Yes" : "No"}</td>
                <td><button className="ghost" onClick={() => setEditing(p)}>Edit</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && (
        <Modal title={editing.id ? "Edit rate" : "New rate"} onClose={() => setEditing(null)}>
          <div className="grid3">
            <Field label="Room type"><select value={editing.room_type} onChange={set("room_type")}>{(types.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
            <Field label="Name"><input value={editing.name} onChange={set("name")} /></Field>
            <Field label="Code"><input value={editing.code} onChange={set("code")} /></Field>
            <Field label="Price ETB"><input type="number" value={editing.price_etb} onChange={set("price_etb")} /></Field>
            <Field label="Price USD"><input type="number" value={editing.price_usd} onChange={set("price_usd")} /></Field>
            <Field label="Priority"><input type="number" value={editing.priority} onChange={set("priority")} /></Field>
            <Field label="Season start"><input type="date" value={editing.season_start ?? ""} onChange={set("season_start")} /></Field>
            <Field label="Season end"><input type="date" value={editing.season_end ?? ""} onChange={set("season_end")} /></Field>
          </div>
          <label className="radio"><input type="checkbox" checked={editing.breakfast_included} onChange={set("breakfast_included")} /> Breakfast included</label>
          <label className="radio"><input type="checkbox" checked={editing.is_public} onChange={set("is_public")} /> Sell on website and OTAs</label>
          <label className="radio"><input type="checkbox" checked={editing.is_active} onChange={set("is_active")} /> Active</label>
          <ErrorBox error={error} />
          <div className="modal-actions"><button className="primary" disabled={busy} onClick={save}>Save</button></div>
        </Modal>
      )}
    </div>
  );
}

function Channels() {
  const channels = useApi<any[]>("/channels/");
  const logs = useApi<any[]>("/channel-logs/");
  const { error, run } = useAction();
  const act = (fn: () => Promise<unknown>) => run(async () => { await fn(); channels.reload(); logs.reload(); });
  return (
    <div className="card stack">
      <p className="muted">Availability comes from the same booking table as the front desk, so OTA, website and walk-in bookings can never take the same last room. Use stop-sell on go-live day.</p>
      <ErrorBox error={error} />
      <table>
        <thead><tr><th>Channel</th><th>Active</th><th>Stop sell</th><th>Markup</th><th>Last push</th><th>Webhook</th><th /></tr></thead>
        <tbody>
          {(channels.data ?? []).map((c) => (
            <tr key={c.id}>
              <td>{c.name}</td>
              <td><input type="checkbox" checked={c.is_active} onChange={(e) => act(() => patch(`/channels/${c.id}/`, { is_active: e.target.checked }))} /></td>
              <td><input type="checkbox" checked={c.stop_sell} onChange={(e) => act(() => post(`/channels/${c.id}/stop-sell/`, { stop_sell: e.target.checked }))} /></td>
              <td>{c.rate_markup_pct}%</td>
              <td>{dateTime(c.last_push_at) || "never"}</td>
              <td><code>/api/channels/webhook/{c.code}/</code></td>
              <td><button onClick={() => act(() => post(`/channels/${c.id}/push/`, { days: 30 }))}>Push 30 days</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Sync log</h3>
      <table>
        <thead><tr><th>When</th><th>Channel</th><th>Event</th><th>Result</th></tr></thead>
        <tbody>{(logs.data ?? []).slice(0, 20).map((l) => <tr key={l.id}><td>{dateTime(l.at)}</td><td>{l.channel_name}</td><td>{l.direction}</td><td>{l.ok ? "OK" : "Failed"} {l.message}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

function StaffList() {
  const staff = useApi<any[]>("/staff/");
  const roles = useApi<any[]>("/staff/roles/");
  const [editing, setEditing] = useState<any | null>(null);
  const { busy, error, run } = useAction();
  const set = (k: string) => (e: any) => setEditing({ ...editing, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const save = () => run(async () => {
    const body = { ...editing };
    if (!body.password) delete body.password;
    if (!body.pin) delete body.pin;
    if (editing.id) await patch(`/staff/${editing.id}/`, body);
    else await post("/staff/", body);
    setEditing(null);
    staff.reload();
  });
  return (
    <div className="card">
      <div className="section-head"><h2>Staff</h2><button onClick={() => setEditing({ username: "", first_name: "", last_name: "", role: "front_desk", preferred_language: "en", is_active: true, password: "", pin: "" })}>Add staff</button></div>
      <table>
        <thead><tr><th>Username</th><th>Name</th><th>Role</th><th>PIN</th><th>Last login</th><th>Active</th><th /></tr></thead>
        <tbody>
          {(staff.data ?? []).map((s) => (
            <tr key={s.id} className={s.is_active ? "" : "void"}>
              <td>{s.username}</td><td>{s.first_name} {s.last_name}</td><td>{s.role.replace(/_/g, " ")}</td><td>{s.has_pin ? "Set" : "–"}</td>
              <td>{dateTime(s.last_login)}</td><td>{s.is_active ? "Yes" : "No"}</td>
              <td><button className="ghost" onClick={() => setEditing({ ...s, password: "", pin: "" })}>Edit</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {editing && (
        <Modal title={editing.id ? `Edit ${editing.username}` : "New staff member"} onClose={() => setEditing(null)}>
          <div className="grid3">
            <Field label="Username"><input value={editing.username} onChange={set("username")} disabled={!!editing.id} /></Field>
            <Field label="First name"><input value={editing.first_name} onChange={set("first_name")} /></Field>
            <Field label="Last name"><input value={editing.last_name} onChange={set("last_name")} /></Field>
            <Field label="Role"><select value={editing.role} onChange={set("role")}>{(roles.data ?? []).map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}</select></Field>
            <Field label="Language"><select value={editing.preferred_language} onChange={set("preferred_language")}><option value="en">English</option><option value="am">Amharic</option></select></Field>
            <Field label="Phone"><input value={editing.phone ?? ""} onChange={set("phone")} /></Field>
            <Field label={editing.id ? "New password (optional)" : "Password"}><input type="password" value={editing.password} onChange={set("password")} /></Field>
            <Field label="PIN (4–6 digits)"><input inputMode="numeric" value={editing.pin} onChange={set("pin")} /></Field>
          </div>
          <label className="radio"><input type="checkbox" checked={editing.is_active} onChange={set("is_active")} /> Active</label>
          <ErrorBox error={error} />
          <div className="modal-actions"><button className="primary" disabled={busy} onClick={save}>Save</button></div>
        </Modal>
      )}
    </div>
  );
}
