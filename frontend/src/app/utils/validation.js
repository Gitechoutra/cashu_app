/** Client-side validation — mirrors backend/portal/helpers/validators.py for UX.
 *  Advisory only: the server re-validates everything. Each fn returns an error
 *  string or "" when valid. */

const AMOUNT_RE = /^\d+(\.\d{1,2})?$/;
const MAX_AMOUNT = 9999999999.99;

export const cleanAmount = (v) => String(v ?? "").replace(/,/g, "").trim();

export function validateMobile(v) {
  const d = String(v || "").replace(/[\s-]/g, "").replace(/^\+?91(?=\d{10}$)/, "");
  return /^[6-9]\d{9}$/.test(d) ? "" : "Enter a valid 10-digit Indian mobile number.";
}

export const validateOtp = (v) => (/^\d{6}$/.test(String(v || "")) ? "" : "Enter the 6-digit OTP.");

export function validatePin(v) {
  const s = String(v || "");
  if (!/^\d{4,6}$/.test(s)) return "PIN must be 4 to 6 digits.";
  if (new Set(s).size === 1 || "0123456789".includes(s) || "9876543210".includes(s)) {
    return "Choose a less predictable PIN (no repeated or sequential digits).";
  }
  return "";
}

export function validateName(v) {
  const s = String(v || "").trim();
  if (!s) return "Name is required.";
  return /^[A-Za-z][A-Za-z .'-]{0,99}$/.test(s) ? "" : "Use letters, spaces, dots, apostrophes or hyphens only.";
}

export const validateLast4 = (v) => (/^\d{4}$/.test(String(v || "")) ? "" : "Enter exactly the last 4 digits of your card.");

export function validateNickname(v) {
  const s = String(v || "").trim();
  if (!s) return "Card nickname is required.";
  return /^[A-Za-z0-9 .,'&()_-]{1,40}$/.test(s) ? "" : "Nickname: up to 40 letters, numbers or basic punctuation.";
}

export function validateAmount(v, label, { required = false, allowZero = true } = {}) {
  const s = cleanAmount(v);
  if (!s) return required ? `${label} is required.` : "";
  if (!/^\d+(\.\d+)?$/.test(s)) return `${label} must be a positive amount in rupees.`;
  if (!AMOUNT_RE.test(s)) return `${label} can have at most 2 decimal places.`;
  if (Number(s) > MAX_AMOUNT) return `${label} is too large.`;
  if (!allowZero && Number(s) === 0) return `${label} must be greater than zero.`;
  return "";
}

export function validateDate(v, label, { pastDays = 400, futureDays = 120, today = new Date() } = {}) {
  if (!v) return "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return `${label} must be a valid date.`;
  const d = new Date(`${v}T00:00:00`);
  if (Number.isNaN(d.getTime())) return `${label} must be a valid date.`;
  const t = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const diff = Math.round((d - t) / 86400000);
  if (diff < -pastDays || diff > futureDays) return `${label} is outside the allowed range.`;
  return "";
}

/** Validates the manual-card form; returns { field: message } (empty = valid). */
export function validateCardForm(f, { requireIssuerName = false } = {}) {
  const e = {};
  const put = (k, msg) => { if (msg) e[k] = msg; };
  if (requireIssuerName) {
    put("issuer_name", /^[A-Za-z0-9 .,'&()-]{2,100}$/.test(String(f.issuer_name || "").trim()) ? "" : "Enter a valid bank name.");
  }
  put("card_nickname", validateNickname(f.card_nickname));
  put("last_four_digits", validateLast4(f.last_four_digits));
  put("credit_limit", validateAmount(f.credit_limit, "Total credit limit", { required: true, allowZero: false }));
  put("outstanding_balance", validateAmount(f.outstanding_balance, "Outstanding balance"));
  put("available_credit", validateAmount(f.available_credit, "Available credit"));
  put("minimum_amount_due", validateAmount(f.minimum_amount_due, "Minimum amount due"));
  if (f.billing_day !== "" && f.billing_day !== undefined && f.billing_day !== null) {
    const n = Number(f.billing_day);
    if (!Number.isInteger(n) || n < 1 || n > 31) e.billing_day = "Billing cycle date must be between 1 and 31.";
  }
  put("due_date", validateDate(f.due_date, "Payment due date"));

  const num = (k) => (e[k] || cleanAmount(f[k]) === "" ? null : Number(cleanAmount(f[k])));
  const lim = num("credit_limit"), out = num("outstanding_balance"), av = num("available_credit"), md = num("minimum_amount_due");
  if (lim !== null && av !== null && av > lim) e.available_credit = "Available credit cannot exceed the total credit limit.";
  if (out !== null && md !== null && md > out) e.minimum_amount_due = "Minimum amount due cannot exceed the outstanding balance.";
  if (lim !== null && out !== null && out > lim * 2) e.outstanding_balance = "Outstanding balance looks too high for this credit limit — please check.";
  return e;
}

/** Live preview numbers for the manual form (display only). */
export function previewFigures(f) {
  const lim = Number(cleanAmount(f.credit_limit));
  const out = Number(cleanAmount(f.outstanding_balance));
  const rep = cleanAmount(f.available_credit);
  const hasLim = AMOUNT_RE.test(cleanAmount(f.credit_limit)) && lim > 0;
  const hasOut = AMOUNT_RE.test(cleanAmount(f.outstanding_balance));
  return {
    utilization: hasLim && hasOut ? Math.max(0, (out / lim) * 100) : null,
    available: AMOUNT_RE.test(rep) ? Number(rep) : hasLim && hasOut ? Math.max(lim - out, 0) : null,
    availableBasis: AMOUNT_RE.test(rep) ? "REPORTED" : hasLim && hasOut ? "ESTIMATED" : "UNKNOWN",
  };
}

export function validatePayment(amount, outstanding) {
  const err = validateAmount(amount, "Payment amount", { required: true, allowZero: false });
  if (err) return err;
  const n = Number(cleanAmount(amount));
  if (n < 1) return "Minimum payment is ₹1.00.";
  if (outstanding !== null && outstanding !== undefined && n > Number(outstanding)) {
    return "Amount cannot exceed the outstanding balance.";
  }
  return "";
}
