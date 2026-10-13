/** Display formatting. Amounts arrive from the API as 2-dp strings; Number() is
 *  used for display only — never for arithmetic that is sent back. */

export const fmtINR = (v, { compact = false } = {}) => {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  if (compact && Math.abs(n) >= 100000) {
    return `₹${(n / 100000).toLocaleString("en-IN", { maximumFractionDigits: 2 })}L`;
  }
  return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const fmtDate = (s) => {
  if (!s) return "—";
  const d = new Date(s.length === 10 ? `${s}T00:00:00` : s);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
};

export const fmtDateTime = (s) => {
  if (!s) return "—";
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? "—"
    : d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

export const timeAgo = (s, now = Date.now()) => {
  if (!s) return "—";
  const sec = Math.round((now - new Date(s).getTime()) / 1000);
  if (!Number.isFinite(sec)) return "—";
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} h ago`;
  return `${Math.floor(sec / 86400)} d ago`;
};

export const daysUntil = (iso, today = new Date()) => {
  if (!iso) return null;
  const a = new Date(`${iso}T00:00:00`);
  const b = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((a - b) / 86400000);
};

export const BILL_STATUS = {
  NO_DUES:           { label: "No dues",            cls: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" },
  DUE:               { label: "Due",                cls: "bg-sky-500/10 text-sky-300 border-sky-500/20" },
  DUE_SOON:          { label: "Due soon",           cls: "bg-amber-500/10 text-amber-300 border-amber-500/20" },
  OVERDUE:           { label: "Overdue",            cls: "bg-red-500/10 text-red-300 border-red-500/20" },
  PAYMENT_INITIATED: { label: "Payment initiated",  cls: "bg-violet-500/10 text-violet-300 border-violet-500/20" },
  UNKNOWN:           { label: "Status unknown",     cls: "bg-white/5 text-gray-400 border-white/10" },
};

export const PAYMENT_STATUS = {
  CREATED: { label: "Awaiting payment", cls: "bg-white/5 text-gray-300 border-white/10" },
  PENDING: { label: "Pending",          cls: "bg-amber-500/10 text-amber-300 border-amber-500/20" },
  SUCCESS: { label: "Successful",       cls: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" },
  FAILED:  { label: "Failed",           cls: "bg-red-500/10 text-red-300 border-red-500/20" },
};

export const SETTLEMENT_LABEL = {
  NOT_STARTED: "Not started",
  NOT_CONFIGURED: "Issuer not credited — bill-settlement (BBPS) partner not configured",
  PENDING: "Being credited to your card issuer",
  SETTLED: "Credited to your card issuer",
  FAILED: "Issuer credit failed — contact support",
};

export const utilColor = (pct) => {
  if (pct === null || pct === undefined) return "bg-gray-600";
  const n = Number(pct);
  if (n < 10) return "bg-emerald-400";
  if (n < 30) return "bg-cyan-400";
  if (n < 50) return "bg-amber-400";
  return "bg-red-400";
};
