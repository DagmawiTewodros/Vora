import { useState } from "react";
import { Badge, ErrorBox, Field, Modal } from "../components/ui";
import { post } from "../lib/api";
import { birr, dateTime } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

const NEXT: Record<string, string> = { received: "Start processing", in_process: "Mark ready", ready: "Deliver & bill" };

export default function Laundry() {
  const { t } = useI18n();
  const [status, setStatus] = useState("");
  const tickets = useApi<any[]>(`/laundry/tickets/${status ? `?status=${status}` : ""}`, [status]);
  const [creating, setCreating] = useState(false);
  const action = useAction();

  return (
    <div className="page">
      <div className="page-head">
        <h1>{t("Laundry")}</h1>
        <button className="primary" onClick={() => setCreating(true)}>New ticket</button>
      </div>
      <div className="filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All</option><option value="received">Received</option><option value="in_process">In process</option>
          <option value="ready">Ready</option><option value="delivered">Delivered</option>
        </select>
      </div>
      <ErrorBox error={tickets.error || action.error} />
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Ticket</th><th>Room</th><th>Items</th><th>Total</th><th>Status</th><th /></tr></thead>
          <tbody>
            {(tickets.data ?? []).map((tk) => (
              <tr key={tk.id}>
                <td>{tk.number}{tk.express && <span className="badge badge-vip">Express</span>}<small className="block muted">{dateTime(tk.received_at)}</small></td>
                <td>{tk.room_number} <small className="block">{tk.guest_name}</small></td>
                <td>{tk.lines.map((l: any) => `${l.quantity}× ${l.description}`).join(", ")}</td>
                <td>{birr(tk.total)}</td>
                <td><Badge value={tk.status} /></td>
                <td className="row-actions">
                  {NEXT[tk.status] && <button className="primary" onClick={() => action.run(async () => { await post(`/laundry/tickets/${tk.id}/advance/`); tickets.reload(); })}>{NEXT[tk.status]}</button>}
                  {["received", "in_process", "ready"].includes(tk.status) && <button className="ghost" onClick={() => action.run(async () => { await post(`/laundry/tickets/${tk.id}/cancel/`); tickets.reload(); })}>Cancel</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {creating && <NewTicket onClose={() => setCreating(false)} onDone={() => { setCreating(false); tickets.reload(); }} />}
    </div>
  );
}

function NewTicket({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const prices = useApi<any[]>("/laundry/prices/?is_active=true");
  const inHouse = useApi<any[]>("/reservations/?status=checked_in");
  const [reservation, setReservation] = useState<number | null>(null);
  const [qty, setQty] = useState<Record<number, number>>({});
  const [express, setExpress] = useState(false);
  const [notes, setNotes] = useState("");
  const { busy, error, run } = useAction();
  const lines = Object.entries(qty).filter(([, q]) => q > 0).map(([price, quantity]) => ({ price: +price, quantity }));
  const subtotal = lines.reduce((s, l) => s + l.quantity * Number(prices.data?.find((p) => p.id === l.price)?.price ?? 0), 0) * (express ? 1.5 : 1);

  return (
    <Modal title="New laundry ticket" onClose={onClose} wide>
      <Field label="Room / guest">
        <select value={reservation ?? ""} onChange={(e) => setReservation(+e.target.value)}>
          <option value="">Choose…</option>
          {(inHouse.data ?? []).map((r) => <option key={r.id} value={r.id}>{r.room_number} – {r.guest_detail.full_name}</option>)}
        </select>
      </Field>
      <div className="price-list">
        {(prices.data ?? []).map((p) => (
          <label key={p.id} className="price-row">
            <span>{p.item} <small>{p.service_display}</small></span>
            <span>{birr(p.price)}</span>
            <input type="number" min={0} value={qty[p.id] ?? 0} onChange={(e) => setQty({ ...qty, [p.id]: +e.target.value })} />
          </label>
        ))}
      </div>
      <label className="radio"><input type="checkbox" checked={express} onChange={(e) => setExpress(e.target.checked)} /> Express (+50%)</label>
      <Field label="Notes (stains, damage)"><input value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      <p>Estimated before tax: <strong>{birr(subtotal)}</strong></p>
      <ErrorBox error={error} />
      <div className="modal-actions">
        <button className="primary" disabled={busy || !reservation || !lines.length} onClick={() => run(async () => { await post("/laundry/tickets/", { reservation, lines, express, notes }); onDone(); })}>Create ticket</button>
      </div>
    </Modal>
  );
}

