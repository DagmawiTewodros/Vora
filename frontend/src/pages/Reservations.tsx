import { useState } from "react";
import ReservationForm from "../components/ReservationForm";
import { CalendarPlus, CalendarX2 } from "lucide-react";
import { Badge, Empty, ErrorBox, Modal, SkeletonRows } from "../components/ui";
import { post } from "../lib/api";
import { addDays, money, shortDate } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useAsk, useToast } from "../lib/feedback";
import { useI18n } from "../lib/i18n";

export default function Reservations() {
  const { t } = useI18n();
  const settings = useApi("/settings/");
  const today = settings.data?.business_date ?? new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState<string | null>(null);
  const start = from ?? today;
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("active");
  const query = `/reservations/?from=${start}&to=${addDays(start, 30)}${status === "active" ? "&active=true" : status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`;
  const list = useApi<any[]>(settings.data ? query : null, [query]);
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<any | null>(null);
  const action = useAction();

  const ask = useAsk();
  const toast = useToast();
  const cancel = async (r: any, noShow = false) => {
    const reason = await ask({
      title: noShow ? `Mark ${r.code} as no-show?` : `Cancel reservation ${r.code}?`,
      message: `${r.guest_detail.full_name} · ${shortDate(r.check_in)} → ${shortDate(r.check_out)}. The room goes back on sale.`,
      input: { label: "Reason", required: true, initial: noShow ? "Did not arrive" : "" },
      confirmLabel: noShow ? "Mark no-show" : "Cancel reservation",
      danger: true,
    });
    if (reason === null) return;
    action.run(async () => {
      await post(`/reservations/${r.id}/${noShow ? "no-show" : "cancel"}/`, { reason });
      setSelected(null);
      list.reload();
      toast(noShow ? `${r.code} marked as no-show` : `${r.code} cancelled`);
    });
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>{t("Reservations")}</h1>
        <button className="primary" onClick={() => setCreating(true)}>{t("New reservation")}</button>
      </div>
      <div className="filters">
        <input type="date" value={start} onChange={(e) => setFrom(e.target.value)} aria-label="From" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
          <option value="active">Upcoming & in house</option>
          <option value="">All</option>
          <option value="tentative">Tentative</option>
          <option value="confirmed">Confirmed</option>
          <option value="checked_in">Checked in</option>
          <option value="checked_out">Checked out</option>
          <option value="cancelled">Cancelled</option>
          <option value="no_show">No show</option>
        </select>
        <input placeholder={`${t("Search")}: name, phone, code`} value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <ErrorBox error={list.error || action.error} />
      <div className="card">
        {list.data?.length === 0 ? (
          <Empty icon={<CalendarX2 size={28} />} action={<button className="primary" onClick={() => setCreating(true)}><CalendarPlus size={18} aria-hidden="true" />{t("New reservation")}</button>}>
            No reservations in the next 30 days match these filters.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Code</th><th>Guest</th><th>Room</th><th>Dates</th><th>Rate</th><th>Source</th><th>Status</th></tr></thead>
              <tbody>
                {!list.data && <SkeletonRows cols={7} />}
                {(list.data ?? []).map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => setSelected(r)}>
                    <td>{r.code}</td>
                    <td>{r.guest_detail.full_name}</td>
                    <td>{r.room_number ?? "–"} <small className="block muted">{r.room_type_name}</small></td>
                    <td>{shortDate(r.check_in)} → {shortDate(r.check_out)}</td>
                    <td>{money(r.nightly_rate, r.currency)}</td>
                    <td>{r.channel || r.source.replace("_", " ")}</td>
                    <td><Badge value={r.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {creating && (
        <Modal title={t("New reservation")} onClose={() => setCreating(false)} wide>
          <ReservationForm start={today} onDone={() => { setCreating(false); list.reload(); }} />
        </Modal>
      )}
      {selected && (
        <Modal title={`${selected.code} · ${selected.guest_detail.full_name}`} onClose={() => setSelected(null)}>
          <dl className="details">
            <dt>Room type</dt><dd>{selected.room_type_name}</dd>
            <dt>Room</dt><dd>{selected.room_number ?? "Not assigned"}</dd>
            <dt>Dates</dt><dd>{shortDate(selected.check_in)} → {shortDate(selected.check_out)} ({selected.nights} nights)</dd>
            <dt>Guests</dt><dd>{selected.adults} adults, {selected.children} children</dd>
            <dt>Rate</dt><dd>{money(selected.nightly_rate, selected.currency)} / night {selected.breakfast_included && "· breakfast included"}</dd>
            <dt>Source</dt><dd>{selected.channel || selected.source} {selected.external_reference}</dd>
            <dt>Phone</dt><dd>{selected.guest_detail.phone || "–"}</dd>
            <dt>Requests</dt><dd>{selected.special_requests || "–"}</dd>
            <dt>Status</dt><dd><Badge value={selected.status} /></dd>
          </dl>
          <div className="modal-actions">
            {selected.status === "tentative" && (
              <button onClick={() => action.run(async () => { await post(`/reservations/${selected.id}/confirm/`); setSelected(null); list.reload(); })}>Confirm</button>
            )}
            {["tentative", "confirmed"].includes(selected.status) && (
              <>
                <button onClick={() => cancel(selected, true)}>No-show</button>
                <button className="danger" onClick={() => cancel(selected)}>Cancel reservation</button>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
