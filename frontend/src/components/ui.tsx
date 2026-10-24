import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { label } from "../lib/format";

export function ErrorBox({ error }: { error: string | null | undefined }) {
  if (!error) return null;
  return <div className="error" role="alert">{error}</div>;
}

export function Badge({ value, kind }: { value: string; kind?: string }) {
  return <span className={`badge badge-${kind ?? value}`}>{label(value)}</span>;
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Accessible dialog: traps focus, closes on Escape or backdrop, and returns focus to the trigger. */
export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const root = ref.current!;
    const first = root.querySelector(".modal-body")?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? root).focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        close.current();
      } else if (e.key === "Tab") {
        const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
        if (!items.length) return;
        const [head, tail] = [items[0], items[items.length - 1]];
        if (e.shiftKey && document.activeElement === head) { e.preventDefault(); tail.focus(); }
        else if (!e.shiftKey && document.activeElement === tail) { e.preventDefault(); head.focus(); }
      }
    };
    root.addEventListener("keydown", onKey);
    document.body.classList.add("modal-open");
    return () => {
      root.removeEventListener("keydown", onKey);
      // Passive cleanup runs after the dialog left the DOM; keep the lock if another is open.
      if (!document.querySelector(".modal-backdrop")) document.body.classList.remove("modal-open");
      opener?.focus?.();
    };
  }, []);

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div ref={ref} tabIndex={-1} className={`modal ${wide ? "modal-wide" : ""}`} onMouseDown={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close dialog"><X size={20} aria-hidden="true" /></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function Field({ label: text, children, required, hint }: { label: string; children: ReactNode; required?: boolean; hint?: string }) {
  return (
    <label className="field">
      <span>{text}{required && <em className="req" aria-hidden="true"> *</em>}</span>
      {children}
      {hint && <small className="hint">{hint}</small>}
    </label>
  );
}

/** Empty state with an optional icon and a next step, instead of a blank panel. */
export function Empty({ children, icon, action }: { children: ReactNode; icon?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      {icon && <span className="empty-icon" aria-hidden="true">{icon}</span>}
      <p>{children}</p>
      {action}
    </div>
  );
}

export function Stat({ title, value, hint, icon }: { title: string; value: ReactNode; hint?: string; icon?: ReactNode }) {
  return (
    <div className="stat">
      <div className="stat-title">{icon && <span className="stat-icon" aria-hidden="true">{icon}</span>}{title}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

/** Placeholder rows that hold the table's shape while data loads. */
export function SkeletonRows({ rows = 4, cols }: { rows?: number; cols: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r} className="skeleton-row" aria-hidden="true">
          {Array.from({ length: cols }, (_, c) => <td key={c}><span className="skeleton" style={{ width: `${45 + ((r * 7 + c * 13) % 45)}%` }} /></td>)}
        </tr>
      ))}
    </>
  );
}

export function SkeletonBlock({ height = 96, count = 1 }: { height?: number; count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => <div key={i} className="skeleton skeleton-block" style={{ height }} aria-hidden="true" />)}
    </>
  );
}

/** Announces "Loading…" to screen readers while content is busy. */
export function Busy({ busy }: { busy: boolean }) {
  return <span className="sr-only" role="status">{busy ? "Loading…" : ""}</span>;
}
