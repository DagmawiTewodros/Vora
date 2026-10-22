import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ReservationForm from "../components/ReservationForm";
import { Badge, Empty, ErrorBox, Field, Modal } from "../components/ui";
import { patch, post } from "../lib/api";
import { birr, shortDate } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

type Tab = "arrivals" | "in_house" | "departures";

export default function FrontDesk() {
  const { t } = useI18n();
  const board = useApi("/front-desk/");
  const [tab, setTab] = useState<Tab>("arrivals");
  const [checkIn, setCheckIn] = useState<any | null>(null);
  const [checkOut, setCheckOut] = useState<any | null>(null);
  const [move, setMove] = useState<any | null>(null);
  const [walkIn, setWalkIn] = useState(false);

  const rows: any[] = board.data?.[tab] ?? [];
  const done = () => {
    setCheckIn(null);
    setCheckOut(null);
    setMove(null);
    setWalkIn(false);
    board.reload();
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>{t("Front desk")}</h1>
        <div className="actions">
          <a className="button" href="/reports/guest-register" target="_blank" rel="noreferrer">Guest register</a>
          <button className="primary" onClick={() => setWalkIn(true)}>Walk-in</button>
        </div>
      </div>
      <ErrorBox error={board.error} />
      <div className="tabs">
        {(["arrivals", "in_house", "departures"] as Tab[]).map((k) => (
          <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {t(k === "in_house" ? "In house" : k === "arrivals" ? "Arrivals" : "Departures")} ({board.data?.[k]?.length ?? 0})
          </button>
        ))}
      </div>
      <div className="card">
        {rows.length === 0 ? (
          <Empty>Nothing here right now.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Guest</th><th>Room</th><th>Stay</th><th>Source</th><th>Balance</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.guest_detail.full_name}</strong>
                      {r.guest_detail.vip && <span className="badge badge-vip">VIP</span>}
                      <small className="block">{r.code} · {r.guest_detail.nationality}</small>
                    </td>
                    <td>{r.room_number ?? <span className="muted">{r.room_type_name}</span>}</td>
                    <td>{shortDate(r.check_in)} → {shortDate(r.check_out)} <small className="block">{r.nights} nights · {r.adults + r.children} guests</small></td>
                    <td>{r.channel || r.source.replace("_", " ")}</td>
                    <td>{birr(r.balance)}</td>
                    <td><Badge value={r.status} /></td>
                    <td className="row-actions">
                      {tab === "arrivals" && <button className="primary" onClick={() => setCheckIn(r)}>{t("Check in")}</button>}
                      {tab !== "arrivals" && (
                        <>
                          <FolioLink reservation={r.id} />
                          <button onClick={() => setMove(r)}>Move</button>
                          <button className="primary" onClick={() => setCheckOut(r)}>{t("Check out")}</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {checkIn && <CheckInModal reservation={checkIn} onClose={() => setCheckIn(null)} onDone={done} />}
      {checkOut && <CheckOutModal reservation={checkOut} onClose={() => setCheckOut(null)} onDone={done} />}
      {move && <MoveModal reservation={move} onClose={() => setMove(null)} onDone={done} />}
      {walkIn && (
        <Modal title="Walk-in guest" onClose={() => setWalkIn(false)} wide>
          <ReservationForm start={board.data?.business_date} source="walk_in" onDone={done} />
        </Modal>
      )}
    </div>
  );
}

export function FolioLink({ reservation }: { reservation: number }) {
  const folios = useApi<any[]>(`/folios/?reservation=${reservation}&status=open`);
  const folio = folios.data?.find((f) => f.is_primary) ?? folios.data?.[0];
  return folio ? <Link className="button" to={`/folios/${folio.id}`}>Folio</Link> : null;
}

function CheckInModal({ reservation, onClose, onDone }: { reservation: any; onClose: () => void; onDone: () => void }) {
  const rooms = useApi<any[]>(`/reservations/${reservation.id}/free-rooms/`);
  const [room, setRoom] = useState<number | null>(reservation.room);
  const [keys, setKeys] = useState(1);
  const [guest, setGuest] = useState({ ...reservation.guest_detail });
  const { busy, error, run } = useAction();

  const submit = () =>
    run(async () => {
      const g = reservation.guest_detail;
      const changed = ["nationality", "id_type", "id_number", "visa_number", "visa_expiry", "phone"].some((k) => guest[k] !== g[k]);
      if (changed) {
        await patch(`/guests/${g.id}/`, {
          nationality: guest.nationality, id_type: guest.id_type, id_number: guest.id_number,
          visa_number: guest.visa_number, visa_expiry: guest.visa_expiry || null, phone: guest.phone,
        });
      }
      await post(`/reservations/${reservation.id}/check-in/`, { room, key_cards: keys });
      onDone();
    });

  const set = (k: string) => (e: any) => setGuest({ ...guest, [k]: e.target.value });

  return (
    <Modal title={`Check in ${reservation.guest_detail.full_name}`} onClose={onClose} wide>
      <h3>Guest registration</h3>
      <div className="grid3">
        <Field label="Nationality"><input value={guest.nationality} onChange={set("nationality")} /></Field>
        <Field label="ID type">
          <select value={guest.id_type} onChange={set("id_type")}>
            <option value="passport">Passport</option><option value="fayda">Fayda (National ID)</option>
            <option value="kebele">Kebele ID</option><option value="driving">Driving licence</option>
          </select>
        </Field>
        <Field label="ID / passport no."><input value={guest.id_number} onChange={set("id_number")} /></Field>
        <Field label="Visa no."><input value={guest.visa_number} onChange={set("visa_number")} /></Field>
        <Field label="Visa expiry"><input type="date" value={guest.visa_expiry ?? ""} onChange={set("visa_expiry")} /></Field>
        <Field label="Phone"><input value={guest.phone} onChange={set("phone")} /></Field>
      </div>
      <h3>Room ({reservation.room_type_name})</h3>
      <div className="room-picker">
        {(rooms.data ?? []).map((r) => (
          <button key={r.id} type="button" className={`room-chip hk-${r.housekeeping_status} ${room === r.id ? "selected" : ""}`}
            onClick={() => setRoom(r.id)} title={r.housekeeping_status}>
            {r.number}
          </button>
        ))}
        {rooms.data?.length === 0 && <Empty>No free rooms of this type.</Empty>}
      </div>
      <p className="muted">Green = clean / inspected, red = still dirty (cannot check in until housekeeping finishes).</p>
      <Field label="Key cards"><input type="number" min={0} max={5} value={keys} onChange={(e) => setKeys(+e.target.value)} /></Field>
      <ErrorBox error={error} />
      <div className="modal-actions">
        <button onClick={onClose}>Cancel</button>
        <button className="primary" disabled={busy || !room} onClick={submit}>Check in</button>
      </div>
    </Modal>
  );
}

function CheckOutModal({ reservation, onClose, onDone }: { reservation: any; onClose: () => void; onDone: () => void }) {
  const [ready, setReady] = useState<any | null>(null);
  const { busy, error, run } = useAction();

  useEffect(() => {
    run(async () => setReady(await post(`/reservations/${reservation.id}/prepare-check-out/`)));
  }, [reservation.id, run]);
  const balance = Number(ready?.balance ?? 0);

  return (
    <Modal title={`Check out ${reservation.guest_detail.full_name}`} onClose={onClose}>
      {ready ? (
        <>
          <p>Room {ready.room_number} · {shortDate(ready.check_in)} → {shortDate(ready.check_out)}</p>
          <p className="big-number">{birr(balance)}</p>
          <p className="muted">{balance === 0 ? "The bill is settled." : "Take payment on the folio before checking out."}</p>
        </>
      ) : (
        <p>Posting final room charges…</p>
      )}
      <ErrorBox error={error} />
      <div className="modal-actions">
        <FolioLink reservation={reservation.id} />
        <button
          className="primary"
          disabled={busy || !ready || balance !== 0}
          onClick={() => run(async () => { await post(`/reservations/${reservation.id}/check-out/`); onDone(); })}
        >
          Check out
        </button>
      </div>
    </Modal>
  );
}

function MoveModal({ reservation, onClose, onDone }: { reservation: any; onClose: () => void; onDone: () => void }) {
  const types = useApi<any[]>("/room-types/");
  const [roomType, setRoomType] = useState<number>(reservation.room_type);
  const rooms = useApi<any[]>(`/reservations/${reservation.id}/free-rooms/?room_type=${roomType}`, [roomType]);
  const [room, setRoom] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const { busy, error, run } = useAction();
  return (
    <Modal title={`Move ${reservation.guest_detail.full_name} from ${reservation.room_number}`} onClose={onClose}>
      <Field label="Room type">
        <select value={roomType} onChange={(e) => setRoomType(+e.target.value)}>
          {(types.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </Field>
      <div className="room-picker">
        {(rooms.data ?? []).filter((r) => r.id !== reservation.room && r.status === "vacant").map((r) => (
          <button key={r.id} className={`room-chip hk-${r.housekeeping_status} ${room === r.id ? "selected" : ""}`} onClick={() => setRoom(r.id)}>{r.number}</button>
        ))}
      </div>
      <Field label="Reason"><input value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      <ErrorBox error={error} />
      <div className="modal-actions">
        <button onClick={onClose}>Cancel</button>
        <button className="primary" disabled={busy || !room} onClick={() => run(async () => { await post(`/reservations/${reservation.id}/move-room/`, { room, reason }); onDone(); })}>Move</button>
      </div>
    </Modal>
  );
}

