import { useState } from "react";
import { post } from "../lib/api";
import { birr, dateTime } from "../lib/format";
import { useAction, useApi } from "../lib/hooks";
import { ErrorBox, Field, Modal } from "./ui";

/** Shows the cashier's open shift; opening and closing (with cash count) happen here. */
export default function ShiftBar() {
  const shift = useApi("/shifts/current/");
  const [closing, setClosing] = useState(false);
  const [counted, setCounted] = useState({ etb: "", usd: "", notes: "" });
  const [summary, setSummary] = useState<any | null>(null);
  const action = useAction();

  const open = () => {
    const float = window.prompt("Opening cash float (ETB)", "0");
    if (float === null) return;
    action.run(async () => { await post("/shifts/", { opening_float: float || "0" }); shift.reload(); });
  };

  return (
    <div className="shift-bar">
      {shift.data ? (
        <>
          <span>Shift open since {dateTime(shift.data.opened_at)} · float {birr(shift.data.opening_float)}</span>
          <button onClick={() => setClosing(true)}>Close shift</button>
        </>
      ) : (
        <>
          <span className="muted">No open cashier shift — needed to take payments.</span>
          <button className="primary" onClick={open}>Open shift</button>
        </>
      )}
      <ErrorBox error={action.error} />
      {closing && shift.data && (
        <Modal title="Close cashier shift" onClose={() => { setClosing(false); setSummary(null); }}>
          {summary ? (
            <div className="stack">
              <p>Payments: {summary.payment_count} · total {birr(summary.total_etb)}</p>
              <p>Expected cash: {birr(summary.expected_cash_etb)} · counted {birr(summary.counted_cash_etb)}</p>
              <p className={Number(summary.over_short_etb) === 0 ? "" : "warn"}>Over / short: {birr(summary.over_short_etb)}</p>
              {Number(summary.expected_cash_usd) > 0 && <p>USD cash expected {summary.expected_cash_usd}, counted {summary.counted_cash_usd}</p>}
              <button className="primary" onClick={() => window.print()}>Print</button>
            </div>
          ) : (
            <>
              <Field label="Counted cash (ETB)"><input type="number" step="0.01" value={counted.etb} onChange={(e) => setCounted({ ...counted, etb: e.target.value })} /></Field>
              <Field label="Counted cash (USD)"><input type="number" step="0.01" value={counted.usd} onChange={(e) => setCounted({ ...counted, usd: e.target.value })} /></Field>
              <Field label="Notes"><input value={counted.notes} onChange={(e) => setCounted({ ...counted, notes: e.target.value })} /></Field>
              <div className="modal-actions">
                <button className="primary" disabled={action.busy || counted.etb === ""} onClick={() => action.run(async () => {
                  setSummary(await post(`/shifts/${shift.data.id}/close/`, { counted_cash_etb: counted.etb, counted_cash_usd: counted.usd || "0", notes: counted.notes }));
                  shift.reload();
                })}>Close shift</button>
              </div>
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
