import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import ShiftBar from "../components/ShiftBar";
import { Badge, ErrorBox } from "../components/ui";
import { post } from "../lib/api";
import { birr, dateTime } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

export default function Folios() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [status, setStatus] = useState("open");
  const [search, setSearch] = useState("");
  const list = useApi<any[]>(`/folios/?status=${status}${search ? `&search=${encodeURIComponent(search)}` : ""}`, [status, search]);
  const action = useAction();

  return (
    <div className="page">
      <div className="page-head">
        <h1>{t("Billing")}</h1>
        <button onClick={() => action.run(async () => navigate(`/folios/${(await post("/folios/walk-in/", { name: "Walk-in customer" })).id}`))}>
          New walk-in bill
        </button>
      </div>
      <ShiftBar />
      <div className="filters">
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="open">Open</option><option value="closed">Closed (invoiced)</option><option value="">All</option>
        </select>
        <input placeholder="Folio, invoice, room, guest" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <ErrorBox error={list.error || action.error} />
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Folio</th><th>Name</th><th>Room</th><th>Total</th><th>{t("Balance")}</th><th>Status</th><th>Invoice</th></tr></thead>
          <tbody>
            {(list.data ?? []).map((f) => (
              <tr key={f.id}>
                <td><Link to={`/folios/${f.id}`}>{f.number}</Link><small className="block muted">{dateTime(f.opened_at)}</small></td>
                <td>{f.name}{!f.is_primary && <small className="block muted">split bill</small>}</td>
                <td>{f.room_number ?? "–"}</td>
                <td>{birr(f.totals.total)}</td>
                <td>{birr(f.totals.balance)}</td>
                <td><Badge value={f.status} /></td>
                <td>{f.invoice_number ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
