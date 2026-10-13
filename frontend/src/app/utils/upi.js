/** UPI QR parsing (NPCI "upi://pay" deep-link format) and safe classification
 *  of anything else a QR code might contain. Pure functions — unit-tested. */

const VPA_RE = /^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z][a-zA-Z0-9]{1,63}$/;
const AMOUNT_RE = /^\d{1,7}(\.\d{1,2})?$/;

const clean = (v, max = 100) =>
  String(v ?? "").replace(/[\u0000-\u001f\u007f<>]/g, "").replace(/\s+/g, " ").trim().slice(0, max);

/**
 * Parse a scanned string. Returns one of:
 *  { kind: "upi", payee: { vpa, name, amount, currency, note, merchantCode, txnRef }, raw }
 *  { kind: "url", url, host }          — http(s) link (never auto-opened)
 *  { kind: "text", text }
 *  { kind: "invalid-upi", reason }     — looks like UPI but fails validation
 */
export function classifyQr(raw) {
  const text = String(raw ?? "").trim();
  if (!text) return { kind: "text", text: "" };

  if (/^upi:\/\//i.test(text)) {
    let u;
    try { u = new URL(text); } catch { return { kind: "invalid-upi", reason: "Malformed UPI code." }; }
    const path = (u.hostname || u.pathname.replace(/^\/+/, "")).toLowerCase();
    if (path !== "pay") return { kind: "invalid-upi", reason: "This UPI code is not a payment request." };
    const p = u.searchParams;
    const vpa = (p.get("pa") || "").trim();
    if (!VPA_RE.test(vpa)) return { kind: "invalid-upi", reason: "The UPI ID in this code is invalid." };
    const am = (p.get("am") || "").trim();
    if (am && (!AMOUNT_RE.test(am) || Number(am) <= 0)) return { kind: "invalid-upi", reason: "The amount in this code is invalid." };
    const cu = (p.get("cu") || "INR").toUpperCase();
    if (cu !== "INR") return { kind: "invalid-upi", reason: "Only INR payments are supported." };
    return {
      kind: "upi",
      raw: text,
      payee: {
        vpa,
        name: clean(p.get("pn"), 80) || null,
        amount: am || null,
        currency: "INR",
        note: clean(p.get("tn"), 80) || null,
        merchantCode: clean(p.get("mc"), 10) || null,
        txnRef: clean(p.get("tr"), 40) || null,
      },
    };
  }

  if (/^https?:\/\//i.test(text)) {
    try {
      const u = new URL(text);
      return { kind: "url", url: u.href, host: u.host };
    } catch { /* fall through */ }
  }
  return { kind: "text", text: text.slice(0, 500) };
}

/**
 * Deep link handed to the user's UPI app. Signed merchant QRs must be passed
 * through unchanged; we only append an amount when the code had none.
 */
export function buildUpiLink(parsed, amount) {
  if (parsed?.kind !== "upi") return null;
  if (parsed.payee.amount || !amount) return parsed.raw;
  if (!AMOUNT_RE.test(String(amount)) || Number(amount) <= 0) return null;
  const sep = parsed.raw.includes("?") ? "&" : "?";
  const cu = /[?&]cu=/i.test(parsed.raw) ? "" : "&cu=INR";
  return `${parsed.raw}${sep}am=${encodeURIComponent(Number(amount).toFixed(2))}${cu}`;
}

export const isValidUpiAmount = (v) => AMOUNT_RE.test(String(v ?? "").trim()) && Number(v) > 0;
