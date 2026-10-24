// App-wide feedback: brief success toasts (announced politely to screen
// readers) and in-app confirm / reason dialogs that replace the browser's
// window.confirm and window.prompt.
import { CheckCircle2, TriangleAlert } from "lucide-react";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Field, Modal } from "../components/ui";

type AskOptions = {
  title: string;
  message?: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  /** Ask for a text value (reason, amount). The promise resolves with it. */
  input?: { label: string; required?: boolean; type?: string; initial?: string; hint?: string };
};
type AskFn = (o: AskOptions) => Promise<string | null>;
type ToastFn = (message: string, tone?: "success" | "error") => void;

const AskCtx = createContext<AskFn>(async () => null);
const ToastCtx = createContext<ToastFn>(() => {});

export const useAsk = () => useContext(AskCtx);
export const useToast = () => useContext(ToastCtx);

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [asking, setAsking] = useState<AskOptions | null>(null);
  const [value, setValue] = useState("");
  const resolver = useRef<(v: string | null) => void>();
  const [toast, setToast] = useState<{ id: number; message: string; tone: "success" | "error" } | null>(null);
  const timer = useRef<number>();

  const ask = useCallback<AskFn>((options) => {
    setValue(options.input?.initial ?? "");
    setAsking(options);
    return new Promise((resolve) => { resolver.current = resolve; });
  }, []);

  const finish = (result: string | null) => {
    setAsking(null);
    resolver.current?.(result);
  };

  const show = useCallback<ToastFn>((message, tone = "success") => {
    window.clearTimeout(timer.current);
    setToast({ id: Date.now(), message, tone });
    timer.current = window.setTimeout(() => setToast(null), 3500);
  }, []);

  const needsValue = !!asking?.input?.required && !value.trim();

  return (
    <AskCtx.Provider value={ask}>
      <ToastCtx.Provider value={show}>
        {children}
        {asking && (
          <Modal title={asking.title} onClose={() => finish(null)}>
            <form className="stack" onSubmit={(e) => { e.preventDefault(); if (!needsValue) finish(asking.input ? value.trim() : "ok"); }}>
              {asking.message && <div className="ask-message">{asking.message}</div>}
              {asking.input && (
                <Field label={asking.input.label} required={asking.input.required} hint={asking.input.hint}>
                  <input type={asking.input.type ?? "text"} value={value} onChange={(e) => setValue(e.target.value)} step={asking.input.type === "number" ? "0.01" : undefined} />
                </Field>
              )}
              <div className="modal-actions">
                <button type="button" onClick={() => finish(null)}>Cancel</button>
                <button type="submit" className={asking.danger ? "danger-solid" : "primary"} disabled={needsValue}>{asking.confirmLabel ?? "Confirm"}</button>
              </div>
            </form>
          </Modal>
        )}
        <div className="toast-region" role="status" aria-live="polite">
          {toast && (
            <div key={toast.id} className={`toast toast-${toast.tone}`}>
              {toast.tone === "success" ? <CheckCircle2 size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
              {toast.message}
            </div>
          )}
        </div>
      </ToastCtx.Provider>
    </AskCtx.Provider>
  );
}
