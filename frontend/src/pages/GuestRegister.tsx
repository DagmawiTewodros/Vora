import { ErrorBox } from "../components/ui";
import { dateTime, shortDate } from "../lib/format";
import { useApi } from "../lib/hooks";

export default function GuestRegister() {
  const { data, error } = useApi("/reports/guest-register/");
  if (!data) return <ErrorBox error={error} />;
  return (
    <div className="invoice register">
      <div className="no-print invoice-tools"><button className="primary" onClick={() => window.print()}>Print</button></div>
      <h1>{data.hotel} – Guest register</h1>
      <p>Night of {shortDate(data.date)} · printed {dateTime(data.printed_at)}</p>
      <table>
        <thead><tr><th>Room</th><th>Name</th><th>Nationality</th><th>ID</th><th>ID no.</th><th>Visa</th><th>Phone</th><th>Arrived</th><th>Departs</th><th>Pax</th></tr></thead>
        <tbody>
          {data.guests.map((g: any, i: number) => (
            <tr key={i}>
              <td>{g.room}</td><td>{g.name}</td><td>{g.nationality}</td><td>{g.id_type}</td><td>{g.id_number}</td>
              <td>{g.visa_number}{g.visa_expiry && ` (exp. ${shortDate(g.visa_expiry)})`}</td><td>{g.phone}</td>
              <td>{shortDate(g.check_in)}</td><td>{shortDate(g.check_out)}</td><td>{g.adults + g.children}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>Total guests: {data.guests.reduce((s: number, g: any) => s + g.adults + g.children, 0)}</p>
    </div>
  );
}
