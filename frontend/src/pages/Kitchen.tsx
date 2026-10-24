import { useEffect } from "react";
import { ChefHat } from "lucide-react";
import { Empty } from "../components/ui";
import { post } from "../lib/api";
import { dateTime } from "../lib/format";
import { useApi } from "../lib/hooks";
import { useI18n } from "../lib/i18n";

export default function Kitchen() {
  const { t } = useI18n();
  const tickets = useApi<any[]>("/pos/kitchen/");
  useEffect(() => {
    const id = window.setInterval(tickets.reload, 10000);
    return () => window.clearInterval(id);
  }, [tickets.reload]);

  const mark = async (id: number, kitchen_status: string) => {
    await post(`/pos/kitchen/items/${id}/`, { kitchen_status });
    tickets.reload();
  };

  return (
    <div className="page">
      <div className="page-head"><h1>{t("Kitchen")}</h1><span className="muted">Refreshes every 10 seconds</span></div>
      <div className="kitchen">
        {(tickets.data ?? []).map((tk) => (
          <div key={tk.order} className="kitchen-ticket card">
            <div className="section-head"><strong>{tk.table || tk.number}</strong><small>{tk.outlet} · {dateTime(tk.sent_at)}</small></div>
            {tk.items.map((i: any) => (
              <div key={i.id} className={`kitchen-item ks-${i.kitchen_status}`}>
                <span>{i.quantity} × {i.name}{i.notes && <small className="block">{i.notes}</small>}</span>
                {i.kitchen_status === "sent" ? <button onClick={() => mark(i.id, "ready")}>Ready</button> : <button className="primary" onClick={() => mark(i.id, "served")}>Served</button>}
              </div>
            ))}
          </div>
        ))}
        {tickets.data?.length === 0 && <Empty icon={<ChefHat size={28} />}>No tickets waiting. New orders appear here automatically.</Empty>}
      </div>
    </div>
  );
}
