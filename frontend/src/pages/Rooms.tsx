import { useState } from "react";
import { Badge, ErrorBox, Modal } from "../components/ui";
import { post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

export default function Rooms() {
  const { t } = useI18n();
  const { user } = useAuth();
  const board = useApi("/housekeeping/rooms/");
  const tasks = useApi<any[]>("/housekeeping/tasks/?open=true");
  const [room, setRoom] = useState<any | null>(null);
  const [floor, setFloor] = useState<string>("all");
  const action = useAction();

  const rooms: any[] = board.data?.rooms ?? [];
  const floors = Array.from(new Set(rooms.map((r) => r.floor))).sort();
  const shown = floor === "all" ? rooms : rooms.filter((r) => String(r.floor) === floor);
  const refresh = () => { board.reload(); tasks.reload(); };

  const act = (fn: () => Promise<unknown>) => action.run(async () => { await fn(); setRoom(null); refresh(); });

  return (
    <div className="page">
      <div className="page-head">
        <h1>{t("Housekeeping")}</h1>
        <div className="legend">
          <span className="hk-dot hk-clean" /> {t("Clean")} {board.data?.counts?.clean ?? 0}
          <span className="hk-dot hk-inspected" /> {t("Inspected")} {board.data?.counts?.inspected ?? 0}
          <span className="hk-dot hk-dirty" /> {t("Dirty")} {board.data?.counts?.dirty ?? 0}
        </div>
      </div>
      <ErrorBox error={board.error || action.error} />
      <div className="tabs">
        <button className={floor === "all" ? "active" : ""} onClick={() => setFloor("all")}>All floors</button>
        {floors.map((f) => (
          <button key={f} className={floor === String(f) ? "active" : ""} onClick={() => setFloor(String(f))}>Floor {f}</button>
        ))}
      </div>
      <div className="rack">
        {shown.map((r) => (
          <button key={r.id} className={`rack-room hk-${r.housekeeping_status} st-${r.status}`} onClick={() => setRoom(r)}>
            <strong>{r.number}</strong>
            <span>{r.room_type_code}</span>
            <small>{r.status === "occupied" ? r.current_guest : t(r.status === "out_of_order" ? "Out of order" : "Vacant")}</small>
          </button>
        ))}
      </div>

      <section className="card">
        <h2>Open tasks</h2>
        <div className="task-list">
          {(tasks.data ?? []).map((task) => (
            <div key={task.id} className={`task prio-${task.priority}`}>
              <div>
                <strong>Room {task.room_number}</strong> · {task.task_type_display}
                <small className="block">{task.assignee_name ? `${task.assignee_name} · ` : ""}{dateTime(task.created_at)} {task.notes}</small>
              </div>
              <Badge value={task.status} />
              {task.status === "open" && <button onClick={() => act(() => post(`/housekeeping/tasks/${task.id}/start/`))}>{t("Start")}</button>}
              <button className="primary" onClick={() => act(() => post(`/housekeeping/tasks/${task.id}/complete/`))}>{t("Done")}</button>
            </div>
          ))}
          {tasks.data?.length === 0 && <p className="muted">All rooms are done.</p>}
        </div>
      </section>

      {room && (
        <Modal title={`Room ${room.number} · ${room.room_type_name}`} onClose={() => setRoom(null)}>
          <p><Badge value={room.status} /> <Badge value={room.housekeeping_status} kind={`hk-${room.housekeeping_status}`} /></p>
          {room.current_guest && <p>Guest: <strong>{room.current_guest}</strong></p>}
          {room.out_of_order_reason && <p>Out of order: {room.out_of_order_reason}</p>}
          <div className="modal-actions wrap">
            {["dirty", "clean", "inspected"].map((s) => (
              <button key={s} disabled={room.housekeeping_status === s}
                onClick={() => act(() => post(`/housekeeping/rooms/${room.id}/set-status/`, { housekeeping_status: s }))}>
                Mark {t(s[0].toUpperCase() + s.slice(1))}
              </button>
            ))}
            {user?.is_manager && room.status === "vacant" && (
              <button className="danger" onClick={() => { const reason = window.prompt("Reason (e.g. plumbing repair)"); if (reason) act(() => post(`/rooms/${room.id}/out-of-order/`, { reason })); }}>
                Out of order
              </button>
            )}
            {user?.is_manager && room.status === "out_of_order" && (
              <button onClick={() => act(() => post(`/rooms/${room.id}/return-to-service/`))}>Return to service</button>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
