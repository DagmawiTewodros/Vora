import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import ShiftBar from "../components/ShiftBar";
import { Badge, ErrorBox, Field, Modal } from "../components/ui";
import { api, patch, post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { birr, dateTime, money, shortDate } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useAsk, useToast } from "../lib/feedback";

const OUTLETS = ["restaurant", "bar", "cafe", "room_service", "minibar", "laundry", "other"];
const METHODS = [
  ["cash", "Cash"], ["card", "Card"], ["telebirr", "Telebirr"], ["cbe_birr", "CBE Birr"],
  ["bank_transfer", "Bank transfer"], ["city_ledger", "Company account"],
];

export default function FolioPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const folio = useApi(`/folios/${id}/`, [id]);
  const rate = useApi("/exchange-rates/current/");
  const [modal, setModal] = useState<"charge" | "payment" | "transfer" | "billto" | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const action = useAction();
  const ask = useAsk();
  const toast = useToast();
  const f = folio.data;
  if (!f) return <div className="page"><ErrorBox error={folio.error} /></div>;

  const done = (data?: any, message?: string) => { if (data) folio.setData(data); else folio.reload(); setModal(null); setSelected([]); if (message) toast(message); };
  const open = f.status === "open";
  const usdRate = Number(rate.data?.usd_to_etb || 0);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Folio {f.number} <Badge value={f.status} /></h1>
          <p className="muted">
            {f.name}{f.room_number && ` · Room ${f.room_number}`}{f.reservation_code && ` · ${f.reservation_code}`}
            {f.bill_to_name && ` · Bill to ${f.bill_to_name} (TIN ${f.bill_to_tin || "–"})`}
          </p>
        </div>
        <div className="actions">
          <Link className="button" to={`/folios/${f.id}/invoice`} target="_blank">{f.invoice_number ? "Invoice" : "Pro-forma"}</Link>
          {open && <button onClick={() => setModal("billto")}>Bill to</button>}
          {open && <button onClick={() => setModal("charge")}>Add charge</button>}
          {open && <button className="primary" onClick={() => setModal("payment")}>Take payment</button>}
        </div>
      </div>
      {open && <ShiftBar />}
      <ErrorBox error={action.error} />

      <section className="stats compact">
        <div className="stat"><div className="stat-title">Charges</div><div className="stat-value">{birr(f.totals.total)}</div><div className="stat-hint">incl. VAT {birr(f.totals.vat)} · SC {birr(f.totals.service_charge)}</div></div>
        <div className="stat"><div className="stat-title">Paid</div><div className="stat-value">{birr(f.totals.paid)}</div></div>
        <div className="stat"><div className="stat-title">Balance</div><div className="stat-value">{birr(f.totals.balance)}</div>
          {usdRate > 0 && <div className="stat-hint">≈ {money(Number(f.totals.balance) / usdRate, "USD")} at {usdRate}</div>}</div>
      </section>

      <section className="card">
        <div className="section-head">
          <h2>Charges</h2>
          {open && selected.length > 0 && <button onClick={() => setModal("transfer")}>Move {selected.length} to another folio</button>}
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr>{open && <th />}<th>Date</th><th>Description</th><th>Qty</th><th>Net</th><th>SC</th><th>VAT</th><th>Total</th><th /></tr></thead>
            <tbody>
              {f.charges.map((c: any) => (
                <tr key={c.id} className={c.is_void ? "void" : ""}>
                  {open && <td>{!c.is_void && <input type="checkbox" checked={selected.includes(c.id)} onChange={(e) => setSelected(e.target.checked ? [...selected, c.id] : selected.filter((x) => x !== c.id))} />}</td>}
                  <td>{shortDate(c.business_date)}</td>
                  <td>{c.description}<small className="block muted">{c.outlet_display}{c.original_currency === "USD" && ` · ${c.original_amount} USD @ ${c.exchange_rate}`}{c.is_void && ` · VOID: ${c.void_reason}`}</small></td>
                  <td>{Number(c.quantity)}</td>
                  <td>{birr(c.net_amount)}</td>
                  <td>{birr(c.service_charge)}</td>
                  <td>{birr(c.vat)}</td>
                  <td>{birr(c.total)}</td>
                  <td>{open && !c.is_void && (user?.is_manager || user?.role === "cashier") && (
                    <button className="ghost danger-text" onClick={async () => {
                      const reason = await ask({ title: `Void "${c.description}"?`, message: `${birr(c.total)} will be removed from the bill. The void is kept in the audit log.`, input: { label: "Reason", required: true }, confirmLabel: "Void charge", danger: true });
                      if (reason) action.run(async () => { await post(`/charges/${c.id}/void/`, { reason }); folio.reload(); toast("Charge voided"); });
                    }}>Void</button>
                  )}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>Payments</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>When</th><th>Method</th><th>Amount</th><th>In ETB</th><th>Reference</th><th>By</th></tr></thead>
            <tbody>
              {f.payments.map((p: any) => (
                <tr key={p.id}>
                  <td>{dateTime(p.received_at)}</td>
                  <td>{p.method_display} {p.kind !== "payment" && <Badge value={p.kind} />}</td>
                  <td>{money(p.amount, p.currency)}</td>
                  <td>{birr(p.amount_etb)}</td>
                  <td>{p.reference}</td>
                  <td>{p.received_by_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {open && Number(f.totals.balance) === 0 && !f.reservation && (
          <button className="primary" onClick={() => action.run(async () => { const closed = await post(`/folios/${f.id}/close/`); folio.setData(closed); toast(`Invoice ${closed.invoice_number} issued`); })}>Close &amp; issue invoice</button>
        )}
      </section>

      {modal === "charge" && <ChargeModal folio={f} onClose={() => setModal(null)} onDone={done} />}
      {modal === "payment" && <PaymentModal folio={f} isManager={!!user?.is_manager} onClose={() => setModal(null)} onDone={done} />}
      {modal === "transfer" && <TransferModal folio={f} charges={selected} onClose={() => setModal(null)} onDone={done} />}
      {modal === "billto" && <BillToModal folio={f} onClose={() => setModal(null)} onDone={done} />}
    </div>
  );
}

function ChargeModal({ folio, onClose, onDone }: any) {
  const [form, setForm] = useState({ outlet: "minibar", description: "", unit_price: "", quantity: "1", currency: "ETB" });
  const { busy, error, run } = useAction();
  return (
    <Modal title="Add charge" onClose={onClose}>
      <Field label="Outlet"><select value={form.outlet} onChange={(e) => setForm({ ...form, outlet: e.target.value })}>{OUTLETS.map((o) => <option key={o} value={o}>{o.replace("_", " ")}</option>)}</select></Field>
      <Field label="Description"><input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
      <div className="grid3">
        <Field label="Unit price (before tax)"><input type="number" step="0.01" value={form.unit_price} onChange={(e) => setForm({ ...form, unit_price: e.target.value })} /></Field>
        <Field label="Quantity"><input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
        <Field label="Currency"><select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}><option>ETB</option><option>USD</option></select></Field>
      </div>
      <ErrorBox error={error} />
      <div className="modal-actions"><button className="primary" disabled={busy} onClick={() => run(async () => onDone(await post(`/folios/${folio.id}/charges/`, form), "Charge posted"))}>Post charge</button></div>
    </Modal>
  );
}

function PaymentModal({ folio, isManager, onClose, onDone }: any) {
  const [form, setForm] = useState({ method: "cash", amount: String(Math.max(Number(folio.totals.balance), 0)), currency: "ETB", reference: "", kind: "payment" });
  const { busy, error, run } = useAction();
  return (
    <Modal title="Take payment" onClose={onClose}>
      <div className="method-grid">
        {METHODS.map(([value, text]) => (
          <button key={value} className={form.method === value ? "selected" : ""} onClick={() => setForm({ ...form, method: value })}>{text}</button>
        ))}
      </div>
      <div className="grid3">
        <Field label="Amount"><input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field>
        <Field label="Currency"><select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}><option>ETB</option><option>USD</option></select></Field>
        <Field label="Type"><select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}><option value="payment">Payment</option><option value="deposit">Deposit</option>{isManager && <option value="refund">Refund</option>}</select></Field>
      </div>
      {form.method !== "cash" && form.method !== "city_ledger" && (
        <Field label="Transaction reference"><input value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} placeholder="Slip / Telebirr / bank ref." /></Field>
      )}
      <ErrorBox error={error} />
      <div className="modal-actions"><button className="primary" disabled={busy} onClick={() => run(async () => onDone(await post(`/folios/${folio.id}/payments/`, form), `${form.kind === "refund" ? "Refund" : "Payment"} of ${form.amount} ${form.currency} recorded`))}>Record payment</button></div>
    </Modal>
  );
}

function TransferModal({ folio, charges, onClose, onDone }: any) {
  const others = useApi<any[]>(folio.reservation ? `/folios/?reservation=${folio.reservation}&status=open` : null);
  const [target, setTarget] = useState<number | null>(null);
  const [newName, setNewName] = useState({ name: "", bill_to_name: "", bill_to_tin: "" });
  const { busy, error, run } = useAction();
  const submit = () => run(async () => {
    let to = target;
    if (!to) to = (await post("/folios/split/", { reservation: folio.reservation, ...newName })).id;
    onDone(await post(`/folios/${folio.id}/transfer/`, { to_folio: to, charges }), `${charges.length} charge(s) moved`);
  });
  return (
    <Modal title="Split bill" onClose={onClose}>
      {(others.data ?? []).filter((o) => o.id !== folio.id).map((o) => (
        <label key={o.id} className="radio"><input type="radio" checked={target === o.id} onChange={() => setTarget(o.id)} /> {o.number} – {o.name}</label>
      ))}
      <label className="radio"><input type="radio" checked={target === null} onChange={() => setTarget(null)} /> New folio</label>
      {target === null && (
        <div className="grid3">
          <Field label="Name"><input value={newName.name} onChange={(e) => setNewName({ ...newName, name: e.target.value })} /></Field>
          <Field label="Company"><input value={newName.bill_to_name} onChange={(e) => setNewName({ ...newName, bill_to_name: e.target.value })} /></Field>
          <Field label="Company TIN"><input value={newName.bill_to_tin} onChange={(e) => setNewName({ ...newName, bill_to_tin: e.target.value })} /></Field>
        </div>
      )}
      {!folio.reservation && <p className="muted">Walk-in bills cannot be split.</p>}
      <ErrorBox error={error} />
      <div className="modal-actions"><button className="primary" disabled={busy || !folio.reservation} onClick={submit}>Move charges</button></div>
    </Modal>
  );
}

function BillToModal({ folio, onClose, onDone }: any) {
  const [form, setForm] = useState({ name: folio.name, bill_to_name: folio.bill_to_name, bill_to_tin: folio.bill_to_tin, display_currency: folio.display_currency });
  const { busy, error, run } = useAction();
  return (
    <Modal title="Invoice details" onClose={onClose}>
      <Field label="Guest / payer name"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
      <Field label="Company name"><input value={form.bill_to_name} onChange={(e) => setForm({ ...form, bill_to_name: e.target.value })} /></Field>
      <Field label="Company TIN"><input value={form.bill_to_tin} onChange={(e) => setForm({ ...form, bill_to_tin: e.target.value })} /></Field>
      <Field label="Show amounts also in"><select value={form.display_currency} onChange={(e) => setForm({ ...form, display_currency: e.target.value })}><option>ETB</option><option>USD</option></select></Field>
      <ErrorBox error={error} />
      <div className="modal-actions"><button className="primary" disabled={busy} onClick={() => run(async () => { await patch(`/folios/${folio.id}/`, form); onDone(await api(`/folios/${folio.id}/`)); })}>Save</button></div>
    </Modal>
  );
}
