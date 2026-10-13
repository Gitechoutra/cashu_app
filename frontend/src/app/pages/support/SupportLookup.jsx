import { useState } from "react";
import { CreditCard, ReceiptText, Search, UserRound } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Button, Field, Pill, inputCls } from "../../components/ui";
import { TICKET_STATUS } from "../../components/TicketThread";
import { PAYMENT_STATUS, SETTLEMENT_LABEL, fmtDate, fmtDateTime, fmtINR } from "../../utils/format";

/** Find a customer by mobile or a payment by reference. Read-only, masked, audit-logged. */
export function SupportLookup() {
  const { api } = useAuth();
  const [mode, setMode] = useState("mobile");
  const [value, setValue] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const search = async (e) => {
    e.preventDefault();
    const v = value.trim();
    if (!v) return;
    setBusy(true); setErr(""); setRes(null);
    const r = await api(`/support/lookup?${new URLSearchParams({ [mode === "mobile" ? "mobile" : "reference"]: v })}`);
    setBusy(false);
    if (r.ok) setRes(r.data); else setErr(r.message);
  };

  return (
    <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2"><Search className="w-5 h-5 text-violet-300" /> Customer lookup</h1>
        <p className="text-sm text-gray-500">Every lookup is recorded in the audit log.</p>
      </div>
      <form onSubmit={search} className="bg-[#0C1220] border border-white/5 rounded-2xl p-4 space-y-3">
        <div className="flex gap-2">
          {[["mobile", "Mobile number", UserRound], ["reference", "Payment reference", ReceiptText]].map(([m, l, I]) => (
            <button type="button" key={m} onClick={() => { setMode(m); setRes(null); setErr(""); }}
              className={`flex-1 flex items-center justify-center gap-2 text-xs px-3 py-2 rounded-xl border ${mode === m ? "border-violet-500/40 bg-violet-500/10 text-violet-200" : "border-white/10 text-gray-400"}`}>
              <I className="w-3.5 h-3.5" /> {l}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <Field label={mode === "mobile" ? "10-digit mobile number" : "Receipt no. / Razorpay order or payment id"}>
              <input className={inputCls(err)} value={value} onChange={(e) => setValue(e.target.value)}
                inputMode={mode === "mobile" ? "numeric" : "text"} placeholder={mode === "mobile" ? "98765 43210" : "CV2610… / order_… / pay_…"} />
            </Field>
          </div>
          <Button type="submit" className="self-end" loading={busy}>Search</Button>
        </div>
        {err && <p className="text-sm text-red-300">{err}</p>}
      </form>

      {res?.customer && res.cards && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-5 text-sm">
            <div className="text-xs text-gray-500 mb-2">Customer</div>
            <div className="text-white font-semibold">{res.customer.full_name || "—"}</div>
            <div className="text-gray-400 text-xs">{res.customer.mobile_number} · {res.customer.status}</div>
            <div className="text-gray-600 text-[11px] mt-1">Member since {fmtDate(res.customer.member_since)} · last login {fmtDateTime(res.customer.last_login)}</div>
            <div className="text-xs text-gray-500 mt-4 mb-2">Tickets</div>
            {(res.tickets || []).length === 0 ? <p className="text-xs text-gray-600">None.</p> : res.tickets.map((t) => (
              <div key={t.ticket_id} className="flex items-center justify-between gap-2 py-1 text-xs">
                <span className="text-gray-300 truncate"><span className="font-mono text-gray-500">{t.reference}</span> {t.subject}</span>
                <Pill className={(TICKET_STATUS[t.status] || TICKET_STATUS.OPEN).cls}>{(TICKET_STATUS[t.status] || TICKET_STATUS.OPEN).label}</Pill>
              </div>
            ))}
          </div>
          <div className="space-y-4">
            <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-5">
              <div className="text-xs text-gray-500 mb-2 flex items-center gap-1.5"><CreditCard className="w-3.5 h-3.5" /> Cards</div>
              {res.cards.length === 0 ? <p className="text-xs text-gray-600">No cards.</p> : res.cards.map((c, i) => (
                <div key={i} className="py-1.5 text-xs"><div className="text-gray-200">{c.issuer_name} · {c.card_nickname} {c.masked_number}</div>
                  <div className="text-gray-500">{c.source === "USER_ENTERED" ? "User-entered" : c.verification_status} · due {fmtDate(c.due_date)}</div></div>
              ))}
            </div>
            <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-5">
              <div className="text-xs text-gray-500 mb-2">Recent payments</div>
              {res.recent_payments.length === 0 ? <p className="text-xs text-gray-600">None.</p> : res.recent_payments.map((p) => <PaymentRow key={p.payment_id} p={p} />)}
            </div>
          </div>
        </div>
      )}

      {res?.payment && (
        <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-5 space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-bold text-white">{fmtINR(res.payment.amount)}</div>
            <Pill className={(PAYMENT_STATUS[res.payment.status] || PAYMENT_STATUS.CREATED).cls}>{(PAYMENT_STATUS[res.payment.status] || PAYMENT_STATUS.CREATED).label}</Pill>
          </div>
          <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-xs">
            {[["Customer", `${res.customer.full_name || "—"} · ${res.customer.mobile_number}`],
              ["Card", `${res.payment.card_nickname} ${res.payment.masked_number}`],
              ["Receipt", res.payment.receipt_number], ["Order", res.payment.provider_order_id],
              ["Payment id", res.payment.provider_payment_id || "—"], ["Mode", res.payment.provider_mode],
              ["Verified via", res.payment.verified_via || "—"], ["Issuer credit", SETTLEMENT_LABEL[res.payment.settlement_status]],
              ["Created", fmtDateTime(res.payment.created_at)], ["Completed", fmtDateTime(res.payment.completed_at)]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3"><dt className="text-gray-500">{k}</dt><dd className="text-gray-200 text-right break-all font-mono">{v}</dd></div>
            ))}
          </dl>
          {res.payment.failure_reason && <Banner tone="error">{res.payment.failure_reason}</Banner>}
        </div>
      )}
    </div>
  );
}

function PaymentRow({ p }) {
  const s = PAYMENT_STATUS[p.status] || PAYMENT_STATUS.CREATED;
  return (
    <div className="py-1.5 flex items-center justify-between gap-2 text-xs">
      <div className="min-w-0"><div className="text-gray-200">{fmtINR(p.amount)} · {p.card_nickname}</div><div className="text-gray-500 font-mono truncate">{p.receipt_number}</div></div>
      <Pill className={s.cls}>{s.label}</Pill>
    </div>
  );
}
