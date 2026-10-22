import { useEffect, useMemo, useState } from "react";
import { Badge, ErrorBox, Field, Modal } from "../components/ui";
import ShiftBar from "../components/ShiftBar";
import { api, post } from "../lib/api";
import { birr } from "../lib/format";
import { useAction, useApi, useOnline } from "../lib/hooks";
import { useI18n } from "../lib/i18n";
import { enqueue, queued, syncQueued, uuid } from "../lib/offline";

type Line = { menu_item: number; name: string; price: string; quantity: number; notes: string };

const PAY_METHODS = [["cash", "Cash"], ["card", "Card"], ["telebirr", "Telebirr"], ["cbe_birr", "CBE Birr"]];

export default function Pos() {
  const { t, lang } = useI18n();
  const online = useOnline();
  const outlets = useApi<any[]>("/pos/outlets/");
  const [outlet, setOutlet] = useState<number | null>(null);
  const menu = useApi<any[]>(outlet ? `/pos/menu/?outlets=${outlet}&is_active=true` : null, [outlet]);
  const openOrders = useApi<any[]>(outlet && online ? `/pos/orders/?outlet=${outlet}&status=open` : null, [outlet, online]);
  const [category, setCategory] = useState<string>("All");
  const [order, setOrder] = useState<any | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [table, setTable] = useState("");
  const [settling, setSettling] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const action = useAction();

  useEffect(() => {
    if (!outlet && outlets.data?.length) setOutlet(outlets.data.find((o) => o.is_active)?.id ?? null);
  }, [outlets.data, outlet]);

  const categories = useMemo(() => ["All", ...Array.from(new Set((menu.data ?? []).map((m) => m.category_name ?? "Other")))], [menu.data]);
  const items = (menu.data ?? []).filter((m) => category === "All" || (m.category_name ?? "Other") === category);

  const add = (m: any) => {
    const existing = lines.find((l) => l.menu_item === m.id && !l.notes);
    if (existing) setLines(lines.map((l) => (l === existing ? { ...l, quantity: l.quantity + 1 } : l)));
    else setLines([...lines, { menu_item: m.id, name: lang === "am" && m.name_am ? m.name_am : m.name, price: m.price, quantity: 1, notes: "" }]);
  };

  const existingTotal = (order?.items ?? []).filter((i: any) => !i.is_void).reduce((s: number, i: any) => s + Number(i.line_total), 0);
  const newTotal = lines.reduce((s, l) => s + Number(l.price) * l.quantity, 0);
  const total = existingTotal + newTotal;

  const reset = () => { setOrder(null); setLines([]); setTable(""); openOrders.reload(); };

  /** Make sure the server has the order and every new line; returns the order. */
  const save = async () => {
    const payload = lines.map(({ menu_item, quantity, notes }) => ({ menu_item, quantity, notes }));
    let current = order;
    if (!current) current = await post("/pos/orders/", { outlet, table, items: payload, client_uuid: uuid() });
    else if (payload.length) current = await post(`/pos/orders/${current.id}/items/`, { items: payload });
    setLines([]);
    setOrder(current);
    return current;
  };

  const send = () => action.run(async () => {
    const current = await save();
    setOrder(await post(`/pos/orders/${current.id}/send/`));
    setNotice("Sent to kitchen");
    openOrders.reload();
  });

  const syncNow = () => action.run(async () => {
    const r = await syncQueued();
    setNotice(`Synced ${r.sent} offline order(s)${r.failed ? `, ${r.failed} need attention` : ""}`);
  });

  return (
    <div className="page pos">
      <div className="page-head">
        <h1>{t("POS")}</h1>
        <div className="actions">
          <select value={outlet ?? ""} onChange={(e) => { setOutlet(+e.target.value); reset(); }} aria-label="Outlet">
            {(outlets.data ?? []).filter((o) => o.is_active).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
          {queued().length > 0 && online && <button onClick={syncNow}>Sync {queued().length} offline</button>}
        </div>
      </div>
      {online && <ShiftBar />}
      {!online && <div className="warn-box">Offline: orders are saved on this tablet and sent automatically when the connection returns. Room posting is checked on sync.</div>}
      <ErrorBox error={action.error || menu.error} />
      {notice && <div className="notice" onAnimationEnd={() => setNotice(null)}>{notice}</div>}

      <div className="pos-grid">
        <section>
          <div className="tabs scroll">
            {categories.map((c) => <button key={c} className={category === c ? "active" : ""} onClick={() => setCategory(c)}>{c}</button>)}
          </div>
          <div className="menu-grid">
            {items.map((m) => (
              <button key={m.id} className="menu-item" onClick={() => add(m)}>
                <strong>{lang === "am" && m.name_am ? m.name_am : m.name}</strong>
                {lang !== "am" && m.name_am && <small>{m.name_am}</small>}
                <span>{birr(m.price)}</span>
              </button>
            ))}
          </div>
          {online && (openOrders.data?.length ?? 0) > 0 && (
            <>
              <h3>Open tables</h3>
              <div className="open-orders">
                {openOrders.data!.map((o) => (
                  <button key={o.id} className={order?.id === o.id ? "selected" : ""} onClick={() => { setOrder(o); setLines([]); setTable(o.table); }}>
                    <strong>{o.table || o.number}</strong> <span>{birr(o.subtotal)}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </section>

        <aside className="ticket card">
          <div className="ticket-head">
            <Field label="Table"><input value={table} onChange={(e) => setTable(e.target.value)} disabled={!!order} placeholder="e.g. T4" /></Field>
            {order && <span className="muted">#{order.number}</span>}
          </div>
          <ul>
            {(order?.items ?? []).map((i: any) => (
              <li key={i.id} className={i.is_void ? "void" : ""}>
                <span>{i.quantity} × {i.name}</span>
                <Badge value={i.kitchen_status} />
                <span>{birr(i.line_total)}</span>
              </li>
            ))}
            {lines.map((l, idx) => (
              <li key={`n${idx}`} className="new-line">
                <span>
                  <button className="ghost" onClick={() => setLines(lines.map((x, j) => (j === idx ? { ...x, quantity: Math.max(1, x.quantity - 1) } : x)))}>−</button>
                  {l.quantity}
                  <button className="ghost" onClick={() => setLines(lines.map((x, j) => (j === idx ? { ...x, quantity: x.quantity + 1 } : x)))}>+</button>
                  {l.name}
                </span>
                <button className="ghost" onClick={() => setLines(lines.filter((_, j) => j !== idx))} aria-label="Remove">✕</button>
                <span>{birr(Number(l.price) * l.quantity)}</span>
              </li>
            ))}
          </ul>
          <div className="ticket-total"><span>Subtotal (before VAT &amp; service)</span><strong>{birr(total)}</strong></div>
          <div className="ticket-actions">
            <button disabled={!online || action.busy || (!lines.length && !order)} onClick={send}>{t("Send to kitchen")}</button>
            <button className="primary" disabled={action.busy || (!lines.length && !order?.items?.length)} onClick={() => setSettling(true)}>{t("Pay")} / {t("Post to room")}</button>
            {(order || lines.length > 0) && <button className="ghost" onClick={reset}>Clear</button>}
          </div>
        </aside>
      </div>

      {settling && (
        <SettleModal
          total={total}
          online={online}
          onClose={() => setSettling(false)}
          onSettle={(settlement) => action.run(async () => {
            if (!online) {
              enqueue({ client_uuid: uuid(), outlet: outlet!, table, covers: 1, items: lines.map((l) => ({ menu_item: l.menu_item, quantity: l.quantity, notes: l.notes })), settlement, created_at: new Date().toISOString() });
              setNotice("Saved offline");
            } else {
              const current = await save();
              await post(`/pos/orders/${current.id}/settle/`, settlement);
              setNotice(settlement.type === "room" ? `Posted to room ${settlement.room}` : "Paid");
            }
            setSettling(false);
            reset();
          })}
        />
      )}
    </div>
  );
}

function SettleModal({ total, online, onClose, onSettle }: { total: number; online: boolean; onClose: () => void; onSettle: (s: any) => void }) {
  const settings = useApi(online ? "/settings/" : null);
  const [mode, setMode] = useState<"room" | "direct">("room");
  const [room, setRoom] = useState("");
  const [guest, setGuest] = useState<string | null>(null);
  const [method, setMethod] = useState("cash");
  const [reference, setReference] = useState("");
  const s = settings.data;
  const sc = s ? total * Number(s.service_charge_rate) : 0;
  const vat = s ? (s.vat_on_service_charge ? total + sc : total) * Number(s.vat_rate) : 0;
  const gross = s && !s.prices_include_tax ? total + sc + vat : total;
  const [amount, setAmount] = useState("");

  useEffect(() => {
    if (!online || room.length < 2) return setGuest(null);
    const id = window.setTimeout(() => api(`/folios/?room=${room}&status=open`).then((f) => setGuest(f[0]?.name ?? "No guest checked in")).catch(() => setGuest(null)), 300);
    return () => window.clearTimeout(id);
  }, [room, online]);

  return (
    <Modal title={`Settle ${birr(gross)}`} onClose={onClose}>
      {s && <p className="muted">Subtotal {birr(total)} + service {birr(sc)} + VAT {birr(vat)}</p>}
      <div className="tabs">
        <button className={mode === "room" ? "active" : ""} onClick={() => setMode("room")}>Post to room</button>
        <button className={mode === "direct" ? "active" : ""} onClick={() => setMode("direct")}>Pay now</button>
      </div>
      {mode === "room" ? (
        <>
          <Field label="Room number"><input value={room} onChange={(e) => setRoom(e.target.value)} inputMode="numeric" autoFocus /></Field>
          {guest && <p><strong>{guest}</strong></p>}
          <div className="modal-actions"><button className="primary" disabled={!room} onClick={() => onSettle({ type: "room", room })}>Post to room {room}</button></div>
        </>
      ) : (
        <>
          <div className="method-grid">
            {PAY_METHODS.map(([v, l]) => <button key={v} className={method === v ? "selected" : ""} onClick={() => setMethod(v)}>{l}</button>)}
          </div>
          <Field label="Amount received (ETB)"><input type="number" step="0.01" value={amount} placeholder={gross.toFixed(2)} onChange={(e) => setAmount(e.target.value)} /></Field>
          {method === "cash" && Number(amount) > gross && <p>Change: <strong>{birr(Number(amount) - gross)}</strong></p>}
          {method !== "cash" && <Field label="Reference"><input value={reference} onChange={(e) => setReference(e.target.value)} /></Field>}
          <div className="modal-actions">
            <button className="primary" onClick={() => onSettle({ type: "direct", payments: [{ method, amount: amount || gross.toFixed(2), currency: "ETB", reference }] })}>Confirm payment</button>
          </div>
        </>
      )}
    </Modal>
  );
}
