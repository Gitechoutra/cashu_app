import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, Loader2, ReceiptText, XCircle } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { cleanAmount, validatePayment } from "../../utils/validation";
import { PAYMENT_STATUS, SETTLEMENT_LABEL, fmtDate, fmtDateTime, fmtINR } from "../../utils/format";
import { Banner, Button, Field, Pill, inputCls, useToast } from "../ui";

const CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";
let checkoutPromise = null;
function loadCheckout() {
  if (window.Razorpay) return Promise.resolve(true);
  if (!checkoutPromise) {
    checkoutPromise = new Promise((resolve) => {
      const s = document.createElement("script");
      s.src = CHECKOUT_SRC;
      s.async = true;
      s.onload = () => resolve(true);
      s.onerror = () => { checkoutPromise = null; resolve(false); };
      document.body.appendChild(s);
    });
  }
  return checkoutPromise;
}

const newKey = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`).replace(/[^A-Za-z0-9-]/g, "");

/** Pay one card's bill: amount → review → Razorpay Checkout → server-verified status. */
/** onFinished: refresh data when the payment reaches a final status. onClose: close the dialog (Done). */
export function PayCreditCardBill({ bill, payment, onFinished, onClose }) {
  const { api, user } = useAuth();
  const toast = useToast();
  const remaining = bill.outstanding_balance === null ? null
    : Math.max(Number(bill.outstanding_balance) - Number(bill.paid_in_app_this_cycle || 0), 0);
  const [step, setStep] = useState("amount");
  const [amount, setAmount] = useState(remaining ? remaining.toFixed(2) : "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [txn, setTxn] = useState(null);
  const idemKey = useRef(null);
  const pollTimer = useRef(null);

  useEffect(() => () => clearTimeout(pollTimer.current), []);

  const poll = useCallback(async (paymentId, tries = 0) => {
    const r = await api(`/bills/payments/${paymentId}`);
    if (r.ok) setTxn(r.data.payment);
    const open = r.ok && ["CREATED", "PENDING"].includes(r.data.payment.status);
    if (open && tries < 40) pollTimer.current = setTimeout(() => poll(paymentId, tries + 1), 3000);
    if (r.ok && !open) onFinished?.();
  }, [api, onFinished]);

  const review = () => {
    const e = validatePayment(amount, remaining);
    setErr(e);
    if (e) return;
    idemKey.current = newKey();          // one key per review → retries/double-clicks reuse it
    setStep("review");
  };

  const pay = async () => {
    if (busy) return;
    setBusy(true);
    const r = await api("/bills/payment-session", {
      method: "POST", body: { card_id: bill.card_id, amount: cleanAmount(amount), idempotency_key: idemKey.current },
    });
    if (!r.ok) { setBusy(false); toast("error", r.message); if (r.errors?.amount) { setErr(r.errors.amount); setStep("amount"); } return; }
    const session = r.data;
    setTxn(session.payment);

    if (!(await loadCheckout())) {
      setBusy(false);
      toast("error", "Could not load the payment window. Check your connection and try again.");
      return;
    }
    const rzp = new window.Razorpay({
      ...session.checkout,
      prefill: {},                                     // no PII sent to the gateway from here
      notes: {},
      theme: { color: "#06b6d4" },
      handler: async (resp) => {
        setStep("status");
        const v = await api("/bills/payment-verify", { method: "POST", body: resp });
        if (v.ok) setTxn(v.data.payment);
        else toast("error", v.message);
        poll(session.payment.payment_id);
      },
      modal: {
        ondismiss: () => { setBusy(false); setStep("status"); poll(session.payment.payment_id); },
        confirm_close: true,
      },
    });
    rzp.on("payment.failed", () => { /* final status comes from the server, not this event */ });
    rzp.open();
  };

  if (step === "status" && txn) {
    return <PaymentStatusView txn={txn} onDone={() => { clearTimeout(pollTimer.current); onFinished?.(); onClose?.(); }} />;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-[#141C30]/60 p-4 grid grid-cols-2 gap-3 text-sm">
        <div><div className="text-[11px] text-gray-500">Outstanding</div><div className="text-white font-semibold">{fmtINR(bill.outstanding_balance)}</div></div>
        <div><div className="text-[11px] text-gray-500">Due date</div><div className="text-white">{fmtDate(bill.due_date)}</div></div>
        <div><div className="text-[11px] text-gray-500">Minimum due</div><div className="text-gray-200">{fmtINR(bill.minimum_amount_due)}</div></div>
        <div><div className="text-[11px] text-gray-500">Paid via app this cycle</div><div className="text-gray-200">{fmtINR(bill.paid_in_app_this_cycle)}</div></div>
        <p className="col-span-2 text-[11px] text-gray-500">Source: {bill.source_label}{bill.is_stale ? " · may be out of date" : ""}</p>
      </div>

      {step === "amount" && (
        <>
          <Field label="Payment amount (₹)" error={err}>
            <input className={`${inputCls(err)} text-lg font-semibold`} inputMode="decimal" value={amount} autoFocus
              onChange={(e) => { setAmount(e.target.value.replace(/[^\d.,]/g, "")); setErr(""); }} placeholder="0.00" />
          </Field>
          <div className="flex flex-wrap gap-2">
            {bill.minimum_amount_due && Number(bill.minimum_amount_due) > 0 && (
              <Chip onClick={() => setAmount(Number(bill.minimum_amount_due).toFixed(2))}>Minimum · {fmtINR(bill.minimum_amount_due)}</Chip>
            )}
            {remaining > 0 && <Chip onClick={() => setAmount(remaining.toFixed(2))}>Full due · {fmtINR(remaining)}</Chip>}
          </div>
          {remaining === 0 && <Banner tone="success">No dues left on this card for the current cycle.</Banner>}
          <Button className="w-full" onClick={review} disabled={!payment.configured || remaining === 0}>Review payment</Button>
        </>
      )}

      {step === "review" && (
        <>
          <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/[0.04] p-4 space-y-2 text-sm">
            <Row k="Paying" v={`${bill.issuer_name} · ${bill.card_nickname} (${bill.masked_number})`} />
            <Row k="Amount" v={<span className="text-cyan-300 font-semibold text-base">{fmtINR(cleanAmount(amount))}</span>} />
            <Row k="Payer" v={user?.mobile_number} />
            <Row k="Via" v={`Razorpay${payment.mode === "test" ? " (test mode)" : ""}`} />
          </div>
          {payment.message && <Banner tone="warn" icon={AlertTriangle}>{payment.message}</Banner>}
          <div className="flex gap-2">
            <Button variant="ghost" className="flex-1" onClick={() => setStep("amount")} disabled={busy}>Edit</Button>
            <Button className="flex-1" onClick={pay} loading={busy}>Pay {fmtINR(cleanAmount(amount))}</Button>
          </div>
        </>
      )}
    </div>
  );
}

export function PaymentStatusView({ txn, onDone }) {
  const st = PAYMENT_STATUS[txn.status] || PAYMENT_STATUS.CREATED;
  const Icon = txn.status === "SUCCESS" ? CheckCircle2 : txn.status === "FAILED" ? XCircle : txn.status === "PENDING" ? Clock : Loader2;
  const color = txn.status === "SUCCESS" ? "text-emerald-300" : txn.status === "FAILED" ? "text-red-300" : "text-amber-300";
  return (
    <div className="space-y-4">
      <div className="flex flex-col items-center text-center pt-2">
        <Icon className={`w-12 h-12 ${color} ${txn.status === "CREATED" ? "animate-spin" : ""}`} />
        <div className="text-2xl font-bold text-white mt-3">{fmtINR(txn.amount)}</div>
        <Pill className={`${st.cls} mt-2`}>{st.label}</Pill>
        <p className="text-xs text-gray-500 mt-2 max-w-xs">
          {txn.status === "SUCCESS" ? "Confirmed by Razorpay server-to-server."
            : txn.status === "FAILED" ? (txn.failure_reason || "The payment did not go through. No money was taken, or it will be refunded by your bank.")
            : "Waiting for confirmation from the payment provider. This page updates automatically."}
        </p>
      </div>
      <div className="rounded-xl border border-white/10 bg-[#141C30]/60 p-4 space-y-2 text-xs">
        <div className="flex items-center gap-2 text-gray-300 text-sm mb-1"><ReceiptText className="w-4 h-4" /> Receipt</div>
        <Row k="Receipt no." v={<span className="font-mono">{txn.receipt_number}</span>} />
        <Row k="Card" v={`${txn.card_nickname} ${txn.masked_number}`} />
        <Row k="Order ref" v={<span className="font-mono">{txn.provider_order_id}</span>} />
        {txn.provider_payment_id && <Row k="Payment ref" v={<span className="font-mono">{txn.provider_payment_id}</span>} />}
        {txn.payment_method && <Row k="Method" v={txn.payment_method.toUpperCase()} />}
        <Row k="Created" v={fmtDateTime(txn.created_at)} />
        {txn.completed_at && <Row k="Completed" v={fmtDateTime(txn.completed_at)} />}
        {txn.status === "SUCCESS" && <Row k="Issuer credit" v={SETTLEMENT_LABEL[txn.settlement_status]} />}
        {txn.provider_mode === "test" && <p className="text-amber-300/80 pt-1">Test mode — no real money moved.</p>}
      </div>
      {onDone && <Button className="w-full" variant="ghost" onClick={onDone}>Done</Button>}
    </div>
  );
}

function Row({ k, v }) {
  return <div className="flex items-start justify-between gap-3"><span className="text-gray-500 shrink-0">{k}</span><span className="text-gray-200 text-right break-words [overflow-wrap:anywhere] min-w-0">{v}</span></div>;
}

function Chip({ children, onClick }) {
  return <button type="button" onClick={onClick} className="px-3 py-1.5 text-xs rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:text-cyan-300 hover:border-cyan-500/30">{children}</button>;
}
