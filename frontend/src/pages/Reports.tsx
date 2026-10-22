import { useState } from "react";
import { ErrorBox, Stat } from "../components/ui";
import { addDays, birr, money, shortDate } from "../lib/format";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

export default function Reports() {
  const { t } = useI18n();
  const settings = useApi("/settings/");
  const today = settings.data?.business_date;
  const [range, setRange] = useState<{ start: string; end: string } | null>(null);
  const start = range?.start ?? (today ? addDays(today, -7) : "");
  const end = range?.end ?? (today ? addDays(today, -1) : "");
  const report = useApi(start && end ? `/reports/summary/?start=${start}&end=${end}` : null, [start, end]);
  const [day, setDay] = useState<string | null>(null);
  const daily = useApi(day ? `/reports/daily/?date=${day}` : null, [day]);
  const breakfast = useApi(today ? `/reports/breakfast/?date=${today}` : null, [today]);
  const r = report.data;

  return (
    <div className="page">
      <div className="page-head">
        <h1>{t("Reports")}</h1>
        <div className="actions">
          <a className="button" href="/reports/guest-register" target="_blank" rel="noreferrer">Guest register (police)</a>
          <button onClick={() => window.print()}>Print</button>
        </div>
      </div>
      <div className="filters">
        <label>From <input type="date" value={start} onChange={(e) => setRange({ start: e.target.value, end })} /></label>
        <label>To <input type="date" value={end} onChange={(e) => setRange({ start, end: e.target.value })} /></label>
      </div>
      <ErrorBox error={report.error} />
      {r && (
        <>
          <section className="stats">
            <Stat title="Occupancy" value={`${r.totals.occupancy_pct}%`} hint={`${r.totals.rooms_sold} room nights of ${r.totals.rooms_available}`} />
            <Stat title="ADR" value={birr(r.totals.adr)} hint="Average daily rate (net)" />
            <Stat title="RevPAR" value={birr(r.totals.revpar)} hint="Room revenue per available room" />
            <Stat title="Room revenue" value={birr(r.totals.room_revenue)} />
            <Stat title="All revenue (net)" value={birr(r.totals.total_revenue_net)} />
          </section>
          <section className="card">
            <h2>By day</h2>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Date</th><th>Occupancy</th><th>ADR</th><th>RevPAR</th><th>Net revenue</th><th>VAT</th><th>Service charge</th><th>Arr./Dep.</th></tr></thead>
                <tbody>
                  {r.days.map((d: any) => (
                    <tr key={d.date} className="clickable" onClick={() => setDay(d.date)}>
                      <td>{shortDate(d.date)}</td><td>{d.occupancy_pct}% ({d.rooms_sold})</td><td>{birr(d.adr)}</td><td>{birr(d.revpar)}</td>
                      <td>{birr(d.total_revenue_net)}</td><td>{birr(d.total_vat)}</td><td>{birr(d.total_service_charge)}</td><td>{d.arrivals}/{d.departures}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card">
            <h2>Revenue by outlet</h2>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Outlet</th><th>Net</th><th>Gross (incl. tax)</th></tr></thead>
                <tbody>{r.totals.revenue_by_outlet.map((o: any) => <tr key={o.outlet}><td>{o.label}</td><td>{birr(o.net)}</td><td>{birr(o.total)}</td></tr>)}</tbody>
              </table>
            </div>
          </section>
        </>
      )}
      {daily.data && (
        <section className="card">
          <h2>{shortDate(daily.data.date)} – payments by method</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Method</th><th>Amount</th><th>In ETB</th></tr></thead>
              <tbody>{daily.data.payments.map((p: any, i: number) => <tr key={i}><td>{p.method}</td><td>{money(p.amount, p.currency)}</td><td>{birr(p.amount_etb)}</td></tr>)}</tbody>
            </table>
          </div>
        </section>
      )}
      {breakfast.data && (
        <section className="card">
          <h2>Breakfast today</h2>
          <p>{breakfast.data.covers_taken} covers served of {breakfast.data.entitled_covers} entitled.</p>
        </section>
      )}
    </div>
  );
}
