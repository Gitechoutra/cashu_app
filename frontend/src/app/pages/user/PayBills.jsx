import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { AnimatePresence } from "motion/react";
import { AlertTriangle, CreditCard, IndianRupee, PlugZap, RefreshCw } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { PayCreditCardBill, PaymentStatusView } from "../../components/cards/PayCreditCardBill";
import { Banner, EmptyState, ModalShell, Pill, Skeleton } from "../../components/ui";
import { BankLogo } from "../../components/BankLogo";
import { BILL_STATUS, PAYMENT_STATUS, fmtDate, fmtDateTime, fmtINR } from "../../utils/format";

export function PayBills() {
  const { api } = useAuth();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [viewing, setViewing] = useState(null);
  const selectedId = params.get("card");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    const [b, h] = await Promise.all([api("/bills"), api("/bills/payments?per_page=20")]);
    if (b.ok) setData(b.data); else setErr(b.message);
    if (h.ok) setHistory(h.data.payments);
    setLoading(false);
  }, [api]);
  useEffect(() => { load(); }, [load]);

  const bills = data?.bills || [];
  const payment = data?.payment;
  const selected = bills.find((b) => b.card_id === selectedId);
  const select = (id) => setParams(id ? { card: id } : {}, { replace: true });

  return (
    <div className="p-4 lg:p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Pay bills</h1>
          <p className="text-sm text-gray-500">Choose a card to pay its outstanding amount.</p>
        </div>
        <button onClick={load} aria-label="Refresh" className="p-2 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {err && <Banner tone="error">{err}</Banner>}
      {payment && !payment.configured && (
        <Banner tone="warn" icon={PlugZap}><b>Payment integration not configured.</b> {payment.message !== "Payment integration not configured." && payment.message} You can still view your dues.</Banner>
      )}
      {payment?.configured && payment.mode === "test" && (
        <Banner tone="warn" icon={AlertTriangle}>{payment.message}</Banner>
      )}

      {loading && !data ? (
        <div className="grid sm:grid-cols-2 gap-3">{[0, 1].map((i) => <Skeleton key={i} className="h-28" />)}</div>
      ) : bills.length === 0 ? (
        <EmptyState icon={CreditCard} title="No cards to pay" text="Add a credit card first to see its bills here."
          action={<Link to="/user/cards" className="text-sm text-cyan-300">Go to cards</Link>} />
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {bills.map((b) => {
            const st = BILL_STATUS[b.bill_status] || BILL_STATUS.UNKNOWN;
            return (
              <button key={b.card_id} onClick={() => select(b.card_id)}
                className={`text-left rounded-2xl border p-4 transition-colors bg-[#0C1220] ${b.card_id === selectedId ? "border-cyan-500/50" : "border-white/5 hover:border-white/15"}`}>
                <div className="flex items-center gap-3">
                  <BankLogo code={b.issuer_code} name={b.issuer_name} gradient={b.gradient} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">{b.card_nickname} <span className="text-gray-500">{b.masked_number}</span></div>
                    <div className="text-[11px] text-gray-500 truncate">{b.issuer_name}</div>
                  </div>
                  <Pill className={st.cls}>{st.label}</Pill>
                </div>
                <div className="flex items-end justify-between mt-3">
                  <div><div className="text-[11px] text-gray-500">Outstanding</div><div className="text-lg font-bold text-white">{fmtINR(b.outstanding_balance)}</div></div>
                  <div className="text-right"><div className="text-[11px] text-gray-500">Due</div><div className="text-sm text-gray-200">{fmtDate(b.due_date)}</div></div>
                </div>
                <p className="text-[10px] text-gray-600 mt-2">{b.source_label}</p>
              </button>
            );
          })}
        </div>
      )}

      <section className="bg-[#0C1220] border border-white/5 rounded-2xl overflow-hidden">
        <h2 className="px-5 py-3.5 border-b border-white/5 text-sm font-semibold text-white">Recent payments</h2>
        {history.length === 0 ? <p className="px-5 py-6 text-sm text-gray-500">No payments yet.</p> : (
          <ul className="divide-y divide-white/5">
            {history.map((p) => {
              const s = PAYMENT_STATUS[p.status] || PAYMENT_STATUS.CREATED;
              return (
                <li key={p.payment_id}>
                  <button onClick={() => setViewing(p)} className="w-full px-5 py-3 flex items-center justify-between gap-3 text-sm hover:bg-white/[0.02] text-left">
                    <div className="min-w-0">
                      <div className="text-white truncate">{fmtINR(p.amount)} · {p.card_nickname} {p.masked_number}</div>
                      <div className="text-[11px] text-gray-500 font-mono truncate">{p.receipt_number} · {fmtDateTime(p.created_at)}</div>
                    </div>
                    <Pill className={s.cls}>{s.label}</Pill>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <AnimatePresence>
        {selected && payment && (
          <ModalShell title="Pay credit card bill" subtitle={`${selected.issuer_name} · ${selected.card_nickname} ${selected.masked_number}`}
            onClose={() => { select(null); load(); }}>
            {!payment.configured ? (
              <div className="text-center py-4">
                <PlugZap className="w-8 h-8 text-gray-500 mx-auto mb-2" />
                <p className="text-sm text-white font-semibold">Payment integration not configured.</p>
                <p className="text-xs text-gray-500 mt-1">{payment.message}</p>
              </div>
            ) : (
              <PayCreditCardBill bill={selected} payment={payment} onFinished={load} onClose={() => { select(null); load(); }} />
            )}
          </ModalShell>
        )}
        {viewing && (
          <ModalShell title="Payment details" onClose={() => setViewing(null)}>
            <PaymentLive id={viewing.payment_id} initial={viewing} onDone={() => setViewing(null)} />
          </ModalShell>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Opens a payment and re-checks it with the server (which reconciles with Razorpay). */
function PaymentLive({ id, initial, onDone }) {
  const { api } = useAuth();
  const [p, setP] = useState(initial);
  useEffect(() => {
    let live = true;
    api(`/bills/payments/${id}`).then((r) => { if (live && r.ok) setP(r.data.payment); });
    return () => { live = false; };
  }, [api, id]);
  return <PaymentStatusView txn={p} onDone={onDone} />;
}

export const PayIcon = IndianRupee;
