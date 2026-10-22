import { useState } from "react";
import { Badge, ErrorBox, Field, Modal } from "../components/ui";
import { post } from "../lib/api";
import { birr, shortDate } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

export default function Inventory() {
  const { t } = useI18n();
  const [tab, setTab] = useState<"stock" | "orders">("stock");
  const [low, setLow] = useState(false);
  const items = useApi<any[]>(`/inventory/items/${low ? "?low=true" : ""}`, [low]);
  const orders = useApi<any[]>("/inventory/purchase-orders/");
  const suppliers = useApi<any[]>("/inventory/suppliers/");
  const [moving, setMoving] = useState<any | null>(null);
  const [newPo, setNewPo] = useState(false);
  const action = useAction();
  const reload = () => { items.reload(); orders.reload(); };

  return (
    <div className="page">
      <div className="page-head">
        <h1>{t("Inventory")}</h1>
        <button className="primary" onClick={() => setNewPo(true)}>New purchase order</button>
      </div>
      <div className="tabs">
        <button className={tab === "stock" ? "active" : ""} onClick={() => setTab("stock")}>Stock</button>
        <button className={tab === "orders" ? "active" : ""} onClick={() => setTab("orders")}>Purchase orders</button>
      </div>
      <ErrorBox error={items.error || action.error} />
      {tab === "stock" ? (
        <div className="card">
          <label className="radio"><input type="checkbox" checked={low} onChange={(e) => setLow(e.target.checked)} /> Only items at or below reorder level</label>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Item</th><th>Location</th><th>Stock</th><th>Reorder at</th><th>Unit cost</th><th /></tr></thead>
              <tbody>
                {(items.data ?? []).map((i) => (
                  <tr key={i.id} className={i.needs_reorder ? "low" : ""}>
                    <td>{i.name}<small className="block muted">{i.sku}</small></td>
                    <td>{i.location}</td>
                    <td>{Number(i.stock)} {i.unit} {i.needs_reorder && <span className="badge badge-dirty">Reorder</span>}</td>
                    <td>{Number(i.reorder_level)}</td>
                    <td>{birr(i.unit_cost)}</td>
                    <td><button onClick={() => setMoving(i)}>Issue / count</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card table-wrap">
          <table>
            <thead><tr><th>PO</th><th>Supplier</th><th>Lines</th><th>Total</th><th>Status</th><th /></tr></thead>
            <tbody>
              {(orders.data ?? []).map((po) => (
                <tr key={po.id}>
                  <td>{po.number}<small className="block muted">{shortDate(po.created_at)}</small></td>
                  <td>{po.supplier_name}</td>
                  <td>{po.lines.map((l: any) => `${Number(l.quantity)} ${l.item_name}`).join(", ")}</td>
                  <td>{birr(po.total)}</td>
                  <td><Badge value={po.status} /></td>
                  <td className="row-actions">
                    {po.status === "draft" && <button onClick={() => action.run(async () => { await post(`/inventory/purchase-orders/${po.id}/mark-ordered/`); reload(); })}>Mark ordered</button>}
                    {["draft", "ordered"].includes(po.status) && <button className="primary" onClick={() => action.run(async () => { await post(`/inventory/purchase-orders/${po.id}/receive/`); reload(); })}>Receive all</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {moving && <MoveModal item={moving} onClose={() => setMoving(null)} onDone={() => { setMoving(null); reload(); }} />}
      {newPo && <NewPo items={items.data ?? []} suppliers={suppliers.data ?? []} onClose={() => setNewPo(false)} onDone={() => { setNewPo(false); setTab("orders"); reload(); }} />}
    </div>
  );
}

function MoveModal({ item, onClose, onDone }: any) {
  const [mode, setMode] = useState("issue");
  const [quantity, setQuantity] = useState("");
  const [note, setNote] = useState("");
  const { busy, error, run } = useAction();
  const submit = () => run(async () => {
    if (mode === "count") await post(`/inventory/items/${item.id}/count/`, { counted: quantity, note });
    else await post(`/inventory/items/${item.id}/move/`, { reason: mode, quantity, note });
    onDone();
  });
  return (
    <Modal title={`${item.name} – ${Number(item.stock)} ${item.unit} in stock`} onClose={onClose}>
      <div className="tabs">
        {["issue", "waste", "purchase", "count"].map((m) => <button key={m} className={mode === m ? "active" : ""} onClick={() => setMode(m)}>{m === "count" ? "Stock count" : m[0].toUpperCase() + m.slice(1)}</button>)}
      </div>
      <Field label={mode === "count" ? `Counted quantity (${item.unit})` : `Quantity (${item.unit})`}><input type="number" step="0.001" value={quantity} onChange={(e) => setQuantity(e.target.value)} /></Field>
      <Field label="Note"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder={mode === "issue" ? "e.g. to kitchen" : ""} /></Field>
      <ErrorBox error={error} />
      <div className="modal-actions"><button className="primary" disabled={busy || quantity === ""} onClick={submit}>Save</button></div>
    </Modal>
  );
}

function NewPo({ items, suppliers, onClose, onDone }: any) {
  const [supplier, setSupplier] = useState<number | null>(suppliers[0]?.id ?? null);
  const [lines, setLines] = useState([{ item: items[0]?.id ?? 0, quantity: "1", unit_cost: items[0]?.unit_cost ?? "0" }]);
  const { busy, error, run } = useAction();
  return (
    <Modal title="New purchase order" onClose={onClose} wide>
      <Field label="Supplier">
        <select value={supplier ?? ""} onChange={(e) => setSupplier(+e.target.value)}>{suppliers.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </Field>
      {lines.map((l, i) => (
        <div className="grid3" key={i}>
          <Field label="Item"><select value={l.item} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, item: +e.target.value, unit_cost: items.find((it: any) => it.id === +e.target.value)?.unit_cost ?? x.unit_cost } : x)))}>{items.map((it: any) => <option key={it.id} value={it.id}>{it.name}</option>)}</select></Field>
          <Field label="Quantity"><input type="number" value={l.quantity} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, quantity: e.target.value } : x)))} /></Field>
          <Field label="Unit cost (ETB)"><input type="number" value={l.unit_cost} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, unit_cost: e.target.value } : x)))} /></Field>
        </div>
      ))}
      <button className="ghost" onClick={() => setLines([...lines, { item: items[0]?.id ?? 0, quantity: "1", unit_cost: items[0]?.unit_cost ?? "0" }])}>+ Add line</button>
      <ErrorBox error={error} />
      <div className="modal-actions"><button className="primary" disabled={busy || !supplier} onClick={() => run(async () => { await post("/inventory/purchase-orders/", { supplier, lines }); onDone(); })}>Create draft</button></div>
    </Modal>
  );
}
