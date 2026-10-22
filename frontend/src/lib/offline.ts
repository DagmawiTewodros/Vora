// Queue of POS orders taken while the internet is down. Each order carries a
// client_uuid so re-sending after a flaky connection never double-charges.
import { post } from "./api";

const KEY = "vora.offlineOrders";

export type OfflineOrder = {
  client_uuid: string;
  outlet: number;
  table: string;
  covers: number;
  items: { menu_item: number; quantity: number; notes?: string; name?: string; price?: string }[];
  settlement: { type: "room" | "direct"; room?: string; payments?: { method: string; amount: string; currency: string }[] } | null;
  created_at: string;
  error?: string;
};

export function queued(): OfflineOrder[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

function save(orders: OfflineOrder[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(orders));
  } catch {
    /* storage full or blocked */
  }
}

export function enqueue(order: OfflineOrder) {
  save([...queued(), order]);
}

export function uuid() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}-4000-8000-000000000000`;
}

export async function syncQueued(): Promise<{ sent: number; failed: number }> {
  const orders = queued();
  if (!orders.length) return { sent: 0, failed: 0 };
  const res = await post<{ results: { client_uuid: string; ok: boolean; errors?: unknown }[] }>("/pos/orders/sync/", {
    orders: orders.map(({ error: _e, created_at: _c, ...o }) => ({ ...o, items: o.items.map(({ name: _n, price: _p, ...i }) => i) })),
  });
  const failed = new Map(res.results.filter((r) => !r.ok).map((r) => [r.client_uuid, JSON.stringify(r.errors)]));
  save(orders.filter((o) => failed.has(o.client_uuid)).map((o) => ({ ...o, error: failed.get(o.client_uuid) })));
  return { sent: res.results.length - failed.size, failed: failed.size };
}
