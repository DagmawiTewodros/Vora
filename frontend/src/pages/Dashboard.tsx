import { Navigate } from "react-router-dom";
import { homeFor } from "../components/Layout";
import { ErrorBox, Stat } from "../components/ui";
import { post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { birr, shortDate } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";

export default function Dashboard() {
  const { user } = useAuth();
  const summary = useApi(user?.is_manager ? "/reports/summary/" : null);
  const board = useApi(user?.is_manager ? "/front-desk/" : null);
  const audits = useApi<any[]>(user?.is_manager ? "/reports/night-audits/" : null);
  const audit = useAction();

  if (user && !user.is_manager) return <Navigate to={homeFor(user.role, false)} replace />;

  const days: any[] = summary.data?.days ?? [];
  const last = days[days.length - 2] ?? days[days.length - 1];
  const totals = summary.data?.totals;

  const runAudit = () => {
    if (!window.confirm(`Close business day ${shortDate(board.data?.business_date)}? Room nights will be posted and the date moves forward.`)) return;
    audit.run(async () => {
      await post("/reports/night-audit/run/");
      window.location.reload();
    });
  };

  return (
    <div className="page">
      <div className="page-head">
        <h1>Dashboard</h1>
        <button className="primary" onClick={runAudit} disabled={audit.busy}>Run night audit</button>
      </div>
      <ErrorBox error={summary.error || audit.error} />

      <section className="stats">
        <Stat title="Arrivals today" value={board.data?.arrivals.length ?? "–"} />
        <Stat title="In house" value={board.data?.in_house.length ?? "–"} />
        <Stat title="Departures today" value={board.data?.departures.length ?? "–"} />
        <Stat title="Occupancy (last night)" value={last ? `${last.occupancy_pct}%` : "–"} hint={last && `${last.rooms_sold} of ${last.rooms_available} rooms`} />
        <Stat title="ADR (last night)" value={last ? birr(last.adr) : "–"} />
        <Stat title="RevPAR (last night)" value={last ? birr(last.revpar) : "–"} />
      </section>

      {totals && (
        <section className="card">
          <h2>Last 7 days</h2>
          <div className="stats compact">
            <Stat title="Occupancy" value={`${totals.occupancy_pct}%`} />
            <Stat title="Room revenue" value={birr(totals.room_revenue)} />
            <Stat title="ADR" value={birr(totals.adr)} />
            <Stat title="RevPAR" value={birr(totals.revpar)} />
            <Stat title="All outlets (net)" value={birr(totals.total_revenue_net)} />
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Date</th><th>Occ.</th><th>Rooms</th><th>ADR</th><th>RevPAR</th><th>Revenue (net)</th></tr>
              </thead>
              <tbody>
                {days.map((d) => (
                  <tr key={d.date}>
                    <td>{shortDate(d.date)}</td>
                    <td>{d.occupancy_pct}%</td>
                    <td>{d.rooms_sold}/{d.rooms_available}</td>
                    <td>{birr(d.adr)}</td>
                    <td>{birr(d.revpar)}</td>
                    <td>{birr(d.total_revenue_net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>Revenue by outlet</h3>
          <div className="bars">
            {totals.revenue_by_outlet.map((o: any) => {
              const max = Math.max(...totals.revenue_by_outlet.map((x: any) => Number(x.net)), 1);
              return (
                <div className="bar-row" key={o.outlet}>
                  <span>{o.label}</span>
                  <div className="bar"><div style={{ width: `${(Number(o.net) / max) * 100}%` }} /></div>
                  <strong>{birr(o.net)}</strong>
                </div>
              );
            })}
            {!totals.revenue_by_outlet.length && <p className="muted">No sales posted yet.</p>}
          </div>
        </section>
      )}

      <section className="card">
        <h2>Recent night audits</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Business date</th><th>Run by</th><th>Room nights</th><th>Possible no-shows</th><th>Open shifts</th></tr></thead>
            <tbody>
              {(audits.data ?? []).slice(0, 7).map((a) => (
                <tr key={a.id}>
                  <td>{shortDate(a.business_date)}</td>
                  <td>{a.run_by_name}</td>
                  <td>{a.summary.room_nights_posted}</td>
                  <td>{a.summary.possible_no_shows.join(", ") || "–"}</td>
                  <td>{a.summary.open_cashier_shifts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
