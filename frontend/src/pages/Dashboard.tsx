import { Navigate } from "react-router-dom";
import { homeFor } from "../components/Layout";
import { BedDouble, Coins, Percent, PlaneLanding, PlaneTakeoff, TrendingUp, UtensilsCrossed } from "lucide-react";
import { Empty, ErrorBox, SkeletonBlock, Stat } from "../components/ui";
import { post } from "../lib/api";
import { useAuth } from "../lib/auth";
import { birr, shortDate } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { useAsk } from "../lib/feedback";

/** Occupancy per night as labelled bars; the table below carries the same figures for screen readers. */
function OccupancyChart({ days }: { days: any[] }) {
  if (!days.length) return null;
  const best = days.reduce((a, d) => (d.occupancy_pct > a.occupancy_pct ? d : a), days[0]);
  return (
    <figure className="occ-chart" aria-label={`Occupancy over ${days.length} nights, highest ${best.occupancy_pct}% on ${shortDate(best.date)}`}>
      <figcaption>Occupancy by night</figcaption>
      {days.every((d) => d.rooms_sold === 0) && <p className="muted chart-note">No room nights sold in this period yet. Bars fill in after each night audit.</p>}
      <div className="occ-bars" aria-hidden="true">
        {days.map((d) => (
          <div key={d.date} className="occ-col">
            <span className="occ-value">{d.occupancy_pct}%</span>
            <div className="occ-track"><div className="occ-fill" style={{ height: `${Math.max(d.occupancy_pct, 1.5)}%` }} /></div>
            <span className="occ-day">{new Date(`${d.date}T00:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric" })}</span>
          </div>
        ))}
      </div>
    </figure>
  );
}

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

  const ask = useAsk();
  const runAudit = async () => {
    const ok = await ask({
      title: `Close business day ${shortDate(board.data?.business_date)}?`,
      message: "Room nights are posted to every in-house folio, possible no-shows are flagged, and the business date moves to the next day. This can't be undone.",
      confirmLabel: "Run night audit",
    });
    if (!ok) return;
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

      <section className="stats" aria-busy={!board.data || !summary.data}>
        {!board.data || !summary.data ? <SkeletonBlock count={6} height={104} /> : (
          <>
            <Stat icon={<PlaneLanding size={16} />} title="Arrivals today" value={board.data.arrivals.length} />
            <Stat icon={<BedDouble size={16} />} title="In house" value={board.data.in_house.length} />
            <Stat icon={<PlaneTakeoff size={16} />} title="Departures today" value={board.data.departures.length} />
            <Stat icon={<Percent size={16} />} title="Occupancy" value={last ? `${last.occupancy_pct}%` : "–"} hint={last ? `Last night · ${last.rooms_sold} of ${last.rooms_available} rooms` : "No nights audited yet"} />
            <Stat icon={<Coins size={16} />} title="ADR" value={last ? birr(last.adr) : "–"} hint="Average room rate, last night" />
            <Stat icon={<TrendingUp size={16} />} title="RevPAR" value={last ? birr(last.revpar) : "–"} hint="Revenue per available room" />
          </>
        )}
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
          <OccupancyChart days={days} />
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
            {!totals.revenue_by_outlet.length && <Empty icon={<UtensilsCrossed size={26} />}>No sales posted in the last 7 days.</Empty>}
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
