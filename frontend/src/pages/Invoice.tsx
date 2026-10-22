import { useParams } from "react-router-dom";
import { ErrorBox } from "../components/ui";
import { birr, dateTime, money, shortDate } from "../lib/format";
import { useApi } from "../lib/hooks";

// Printable tax invoice: hotel TIN, buyer TIN, VAT and service charge per line,
// sequential invoice number and the Ethiopian date.
export default function Invoice() {
  const { id } = useParams();
  const { data: inv, error } = useApi(`/folios/${id}/invoice/`, [id]);
  if (!inv) return <ErrorBox error={error} />;
  const pct = (r: string) => `${(Number(r) * 100).toFixed(0)}%`;
  return (
    <div className="invoice">
      <div className="no-print invoice-tools"><button className="primary" onClick={() => window.print()}>Print</button></div>
      <header>
        <div>
          <h1>{inv.hotel.name}</h1>
          <p>{inv.hotel.address}</p>
          <p>{inv.hotel.phone} {inv.hotel.email}</p>
          <p>TIN: <strong>{inv.hotel.tin || "—"}</strong> {inv.hotel.vat_registration_no && `· VAT reg. ${inv.hotel.vat_registration_no}`}</p>
        </div>
        <div className="invoice-meta">
          <h2>{inv.invoice_number ? "TAX INVOICE" : "PRO-FORMA (not a tax invoice)"}</h2>
          {inv.invoice_number && <p>No. <strong>{inv.invoice_number}</strong></p>}
          <p>Folio {inv.folio_number}</p>
          <p>Date: {dateTime(inv.issued_at)}</p>
          {inv.ethiopian_date && <p>{inv.ethiopian_date}</p>}
          {inv.fiscal_receipt_number && <p>Fiscal receipt: {inv.fiscal_receipt_number}</p>}
        </div>
      </header>
      <section className="invoice-parties">
        <div>
          <h3>Guest</h3>
          <p>{inv.guest.name}</p>
          {inv.guest.nationality && <p>{inv.guest.nationality}</p>}
        </div>
        {inv.bill_to.name && (
          <div>
            <h3>Bill to</h3>
            <p>{inv.bill_to.name}</p>
            <p>TIN: {inv.bill_to.tin || "—"}</p>
          </div>
        )}
        {inv.stay && (
          <div>
            <h3>Stay</h3>
            <p>Room {inv.stay.room} · {inv.stay.reservation}</p>
            <p>{shortDate(inv.stay.check_in)} – {shortDate(inv.stay.check_out)} ({inv.stay.nights} nights)</p>
          </div>
        )}
      </section>
      <table>
        <thead><tr><th>Date</th><th>Description</th><th>Qty</th><th>Unit</th><th>Net</th><th>Service {pct(inv.hotel.service_charge_rate)}</th><th>VAT {pct(inv.hotel.vat_rate)}</th><th>Total</th></tr></thead>
        <tbody>
          {inv.lines.map((l: any, i: number) => (
            <tr key={i}>
              <td>{shortDate(l.date)}</td><td>{l.description}</td><td>{Number(l.quantity)}</td><td>{birr(l.unit_price)}</td>
              <td>{birr(l.net)}</td><td>{birr(l.service_charge)}</td><td>{birr(l.vat)}</td><td>{birr(l.total)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr><td colSpan={4}>Totals</td><td>{birr(inv.totals.net)}</td><td>{birr(inv.totals.service_charge)}</td><td>{birr(inv.totals.vat)}</td><td><strong>{birr(inv.totals.total)}</strong></td></tr>
        </tfoot>
      </table>
      <section className="invoice-payments">
        <h3>Payments</h3>
        {inv.payments.map((p: any, i: number) => (
          <p key={i}>{shortDate(p.date)} · {p.method} {p.kind !== "payment" && `(${p.kind})`} · {money(p.amount, p.currency)} {p.currency !== "ETB" && `= ${birr(p.amount_etb)}`} {p.reference}</p>
        ))}
        <p><strong>Balance due: {birr(inv.totals.balance)}</strong></p>
        {inv.usd && <p>USD equivalent at {inv.usd.rate}: total {money(inv.usd.total, "USD")}, balance {money(inv.usd.balance, "USD")}</p>}
      </section>
      <footer>Thank you for staying with us. · Amounts in Ethiopian Birr (ETB).</footer>
    </div>
  );
}
