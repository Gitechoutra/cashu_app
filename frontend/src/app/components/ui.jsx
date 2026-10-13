import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, CheckCircle2, Info, Loader2, X } from "lucide-react";

/* ── Toasts ─────────────────────────────────────────────────────────────── */
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((type, text) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t.slice(-2), { id, type, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed z-[90] bottom-20 lg:bottom-6 inset-x-4 sm:inset-x-auto sm:right-6 flex flex-col gap-2 items-stretch sm:items-end pointer-events-none" aria-live="polite">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div key={t.id}
              initial={{ opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16, scale: 0.97 }}
              className={`pointer-events-auto flex items-start gap-2 px-4 py-3 rounded-xl shadow-2xl border text-sm bg-[#0C1220] max-w-sm ${
                t.type === "success" ? "border-emerald-500/30 text-emerald-200"
                : t.type === "info" ? "border-cyan-500/30 text-cyan-100" : "border-red-500/30 text-red-200"}`}>
              {t.type === "success" ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
                : t.type === "info" ? <Info className="w-4 h-4 mt-0.5 shrink-0" /> : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />}
              <span>{t.text}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

/* ── Modal ──────────────────────────────────────────────────────────────── */
export function ModalShell({ title, subtitle, onClose, children, wide = false, busy = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape" && !busy) onClose?.(); };
    window.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, busy]);
  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center sm:p-4 bg-black/70 backdrop-blur-sm"
      onClick={() => !busy && onClose?.()}>
      <motion.div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}
        initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 40 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        onClick={(e) => e.stopPropagation()}
        className={`bg-[#0C1220] border border-white/10 sm:border-cyan-500/20 rounded-t-3xl sm:rounded-2xl w-full ${wide ? "sm:max-w-2xl" : "sm:max-w-md"} shadow-2xl max-h-[92vh] flex flex-col outline-none`}>
        <div className="px-5 py-4 border-b border-white/5 flex items-start justify-between gap-3 shrink-0">
          <div>
            <h3 className="text-base font-semibold text-white">{title}</h3>
            {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
          </div>
          <button onClick={onClose} disabled={busy} aria-label="Close"
            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-white/10 disabled:opacity-40">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 overflow-y-auto">{children}</div>
      </motion.div>
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel = "Confirm", danger, busy, onConfirm, onClose }) {
  return (
    <ModalShell title={title} onClose={onClose} busy={busy}>
      <p className="text-sm text-gray-300 leading-relaxed">{message}</p>
      <div className="flex gap-2 mt-6">
        <Button variant="ghost" className="flex-1" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} className="flex-1" onClick={onConfirm} loading={busy}>{confirmLabel}</Button>
      </div>
    </ModalShell>
  );
}

/* ── Buttons & fields ───────────────────────────────────────────────────── */
const VARIANTS = {
  primary: "bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-semibold hover:opacity-90 shadow-lg shadow-cyan-500/10",
  ghost: "bg-white/5 border border-white/10 text-gray-200 hover:bg-white/10",
  danger: "bg-red-500/90 text-white font-semibold hover:bg-red-500",
  subtle: "text-gray-400 hover:text-white hover:bg-white/5",
};

export function Button({ variant = "primary", loading, className = "", children, disabled, size = "md", ...props }) {
  const sz = size === "sm" ? "px-3 py-2 text-xs rounded-lg" : "px-4 py-3 text-sm rounded-xl";
  return (
    <button {...props} disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed ${sz} ${VARIANTS[variant]} ${className}`}>
      {loading && <Loader2 className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  );
}

export const inputCls = (err) =>
  `w-full bg-[#141C30] border ${err ? "border-red-500/50" : "border-white/10"} rounded-xl px-3.5 py-3 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-cyan-500/50 focus:ring-2 focus:ring-cyan-500/10 transition-colors`;

export function Field({ label, hint, error, children, optional }) {
  return (
    <label className="block">
      <span className="flex items-center justify-between text-xs text-gray-400 mb-1.5">
        <span>{label}{optional && <span className="text-gray-600"> (optional)</span>}</span>
        {hint && <span className="text-gray-600">{hint}</span>}
      </span>
      {children}
      {error && <span className="mt-1.5 flex items-center gap-1 text-xs text-red-400"><AlertCircle className="w-3.5 h-3.5" />{error}</span>}
    </label>
  );
}

export function Banner({ tone = "info", icon: Icon = Info, children, action }) {
  const tones = {
    info: "bg-cyan-500/5 border-cyan-500/20 text-cyan-100",
    warn: "bg-amber-500/5 border-amber-500/20 text-amber-100",
    error: "bg-red-500/5 border-red-500/20 text-red-200",
    success: "bg-emerald-500/5 border-emerald-500/20 text-emerald-100",
  };
  return (
    <div className={`flex items-start gap-3 px-4 py-3 rounded-xl border text-sm ${tones[tone]}`}>
      <Icon className="w-4 h-4 mt-0.5 shrink-0 opacity-80" />
      <div className="flex-1 leading-relaxed">{children}</div>
      {action}
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-xl bg-white/[0.04] ${className}`} />;
}

export function EmptyState({ icon: Icon, title, text, action }) {
  return (
    <div className="flex flex-col items-center text-center px-6 py-12 rounded-2xl border border-dashed border-white/10 bg-white/[0.015]">
      {Icon && <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-4"><Icon className="w-5 h-5 text-cyan-300" /></div>}
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      {text && <p className="text-sm text-gray-500 mt-1 max-w-sm">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Pill({ className = "", children }) {
  return <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border whitespace-nowrap ${className}`}>{children}</span>;
}
