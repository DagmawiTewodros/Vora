import { useEffect, useState, type FormEvent } from "react";
import { api, post } from "../lib/api";
import { addDays, birr, money } from "../lib/format";
import { useAction } from "../lib/hooks";
import { ErrorBox, Field } from "./ui";

const SOURCES = ["walk_in", "phone", "email", "ota", "direct", "corporate"];
const EMPTY_GUEST = { first_name: "", last_name: "", phone: "", email: "", nationality: "Ethiopia", id_type: "fayda", id_number: "", visa_number: "", company: "", company_tin: "" };

export default function ReservationForm({ start, source = "phone", onDone }: { start: string; source?: string; onDone: (r: any) => void }) {
  const [checkIn, setCheckIn] = useState(start);
  const [checkOut, setCheckOut] = useState(addDays(start, 1));
  const [currency, setCurrency] = useState("ETB");
  const [options, setOptions] = useState<any[]>([]);
  const [roomType, setRoomType] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<any[]>([]);
  const [guest, setGuest] = useState<any | null>(null);
  const [newGuest, setNewGuest] = useState({ ...EMPTY_GUEST });
  const [form, setForm] = useState({ adults: 1, children: 0, source, channel: "", special_requests: "", nightly_rate: "" });
  const { busy, error, setError, run } = useAction();

  useEffect(() => {
    if (checkOut <= checkIn) return;
    api(`/availability/?check_in=${checkIn}&check_out=${checkOut}&currency=${currency}`)
      .then((rows) => {
        setOptions(rows);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, [checkIn, checkOut, currency, setError]);

  useEffect(() => {
    if (query.length < 2) return setMatches([]);
    const id = window.setTimeout(() => api(`/guests/?search=${encodeURIComponent(query)}`).then((g) => setMatches(g.slice(0, 6))), 250);
    return () => window.clearTimeout(id);
  }, [query]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!roomType) return setError("Choose a room type.");
    run(async () => {
      const body: any = {
        room_type: roomType, check_in: checkIn, check_out: checkOut, currency, adults: form.adults, children: form.children,
        source: form.source, channel: form.channel, special_requests: form.special_requests,
      };
      if (form.nightly_rate) body.nightly_rate = form.nightly_rate;
      if (guest) body.guest = guest.id;
      else body.new_guest = newGuest;
      onDone(await post("/reservations/", body));
    });
  };

  const g = (k: keyof typeof EMPTY_GUEST) => ({
    value: newGuest[k],
    onChange: (e: any) => setNewGuest({ ...newGuest, [k]: e.target.value }),
  });

  return (
    <form onSubmit={submit} className="stack">
      <div className="grid3">
        <Field label="Check-in"><input type="date" value={checkIn} onChange={(e) => { setCheckIn(e.target.value); if (checkOut <= e.target.value) setCheckOut(addDays(e.target.value, 1)); }} required /></Field>
        <Field label="Check-out"><input type="date" value={checkOut} min={addDays(checkIn, 1)} onChange={(e) => setCheckOut(e.target.value)} required /></Field>
        <Field label="Currency">
          <select value={currency} onChange={(e) => setCurrency(e.target.value)}><option>ETB</option><option>USD</option></select>
        </Field>
      </div>

      <div className="room-options">
        {options.map((o) => (
          <button type="button" key={o.room_type} disabled={o.available < 1}
            className={`room-option ${roomType === o.room_type ? "selected" : ""}`} onClick={() => setRoomType(o.room_type)}>
            <strong>{o.name}</strong>
            <span>{o.available} left · sleeps {o.capacity}</span>
            <span>{money(o.quote.first_night, currency)} / night · {currency === "ETB" ? birr(o.quote.total) : money(o.quote.total, "USD")}</span>
          </button>
        ))}
      </div>

      <fieldset>
        <legend>Guest</legend>
        {guest ? (
          <div className="chip">
            {guest.full_name} · {guest.phone || guest.email || guest.id_number}
            <button type="button" className="ghost" onClick={() => setGuest(null)}>Change</button>
          </div>
        ) : (
          <>
            <Field label="Find returning guest (name, phone, ID)">
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Type at least 2 letters" />
            </Field>
            {matches.length > 0 && (
              <div className="matches">
                {matches.map((m) => (
                  <button type="button" key={m.id} onClick={() => setGuest(m)}>{m.full_name} <small>{m.phone} {m.nationality}</small></button>
                ))}
              </div>
            )}
            <p className="muted">…or enter a new guest:</p>
            <div className="grid3">
              <Field label="First name"><input {...g("first_name")} required={!guest} /></Field>
              <Field label="Last name"><input {...g("last_name")} /></Field>
              <Field label="Phone"><input {...g("phone")} /></Field>
              <Field label="Email"><input type="email" {...g("email")} /></Field>
              <Field label="Nationality"><input {...g("nationality")} /></Field>
              <Field label="ID type">
                <select {...g("id_type")}>
                  <option value="passport">Passport</option><option value="fayda">Fayda (National ID)</option>
                  <option value="kebele">Kebele ID</option><option value="driving">Driving licence</option>
                </select>
              </Field>
              <Field label="ID / passport no."><input {...g("id_number")} /></Field>
              <Field label="Visa no."><input {...g("visa_number")} /></Field>
              <Field label="Company"><input {...g("company")} /></Field>
            </div>
          </>
        )}
      </fieldset>

      <div className="grid3">
        <Field label="Adults"><input type="number" min={1} value={form.adults} onChange={(e) => setForm({ ...form, adults: +e.target.value })} /></Field>
        <Field label="Children"><input type="number" min={0} value={form.children} onChange={(e) => setForm({ ...form, children: +e.target.value })} /></Field>
        <Field label="Source">
          <select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}>
            {SOURCES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </Field>
        {form.source === "ota" && <Field label="OTA"><input value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })} placeholder="Expedia" /></Field>}
        <Field label={`Rate override (${currency}/night)`}><input type="number" step="0.01" value={form.nightly_rate} onChange={(e) => setForm({ ...form, nightly_rate: e.target.value })} placeholder="Use rate plan" /></Field>
      </div>
      <Field label="Special requests"><textarea rows={2} value={form.special_requests} onChange={(e) => setForm({ ...form, special_requests: e.target.value })} /></Field>
      <ErrorBox error={error} />
      <button className="primary" disabled={busy}>{busy ? "Saving…" : "Save reservation"}</button>
    </form>
  );
}
