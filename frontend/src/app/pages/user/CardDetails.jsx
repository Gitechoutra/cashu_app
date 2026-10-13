import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { AnimatePresence } from "motion/react";
import { ArrowLeft, History, IndianRupee, Info, PencilLine, ReceiptText, RefreshCw, Trash2 } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { CreditCardVisual, UtilizationBar } from "../../components/cards/CreditCardItem";
import { CardVerificationStatus } from "../../components/cards/CardVerificationStatus";
import { ManualCardForm } from "../../components/cards/ManualCardForm";
import { Banner, Button, ConfirmDialog, EmptyState, ModalShell, Pill, Skeleton, useToast } from "../../components/ui";
import { BILL_STATUS, PAYMENT_STATUS, fmtDate, fmtDateTime, fmtINR } from "../../utils/format";

export function CardDetails() {
  const { cardId } = useParams();
  const { api } = useAuth();
  const toast = useToast();
  const nav = useNavigate();
  const [card, setCard] = useState(null);
  const [summary, setSummary] = useState(null);
  const [payments, setPayments] = useState([]);
  const [txns, setTxns] = useState(null);
  const [state, setState] = useState({ loading: true, error: "", notFound: false });
  const [editing, setEditing] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: "" }));
    const id = encodeURIComponent(cardId);
    const [c, s, p, t] = await Promise.all([
      api(`/cards/${id}`), api(`/cards/${id}/summary`), api(`/cards/${id}/payments`), api(`/cards/${id}/transactions`),
    ]);
    if (c.status === 404) return setState({ loading: false, error: "", notFound: true });
    if (!c.ok) return setState({ loading: false, error: c.message, notFound: false });
    setCard(c.data.card);
    setSummary(s.ok ? s.data : null);
    setPayments(p.ok ? p.data.payments : []);
    setTxns(t.ok ? t.data : null);
    setState({ loading: false, error: "", notFound: false });
  }, [api, cardId]);

  useEffect(() => { load(); }, [load]);

  const refresh = async () => {
    setBusy(true);
    const r = await api(`/cards/${encodeURIComponent(cardId)}/refresh`, { method: "POST" });
    setBusy(false);
    if (r.ok) { toast("success", r.data.message); load(); } else { toast("error", r.message); load(); }
  };

  const remove = async () => {
    setBusy(true);
    const r = await api(`/cards/${encodeURIComponent(cardId)}`, { method: "DELETE" });
    setBusy(false);
    if (r.ok) { toast("success", "Card removed."); nav("/user/cards", { replace: true }); }
    else toast("error", r.message);
  };

  if (state.notFound) {
    return (
      <div className="p-4 lg:p-8 max-w-3xl mx-auto">
        <EmptyState title="Card not found" text="It may have been removed, or it doesn't belong to this account."
          action={<Link to="/user/cards" className="text-sm text-cyan-300">Back to cards</Link>} />
      </div>
    );
  }
  if (state.loading && !card) {
    return <div className="p-4 lg:p-8 max-w-5xl mx-auto grid lg:grid-cols-2 gap-6"><Skeleton className="h-56" /><Skeleton className="h-56" /></div>;
  }
  if (state.error && !card) return <div className="p-4 lg:p-8 max-w-3xl mx-auto"><Banner tone="error">{state.error}</Banner></div>;

  const st = BILL_STATUS[card.bill_status] || BILL_STATUS.UNKNOWN;
  return (
    <div className="p-4 lg:p-8 max-w-5xl mx-auto space-y-6">
      <Link to="/user/cards" className="text-xs text-gray-500 hover:text-white inline-flex items-center gap-1"><ArrowLeft className="w-3.5 h-3.5" /> All cards</Link>

      <div className="grid lg:grid-cols-[minmax(0,380px)_1fr] gap-6 items-start">
        <div className="space-y-4">
          <CreditCardVisual card={card} />
          <CardVerificationStatus card={card} />
          <div className="grid grid-cols-2 gap-2">
            <Link to={`/user/bills?card=${card.card_id}`} className="col-span-2 inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-cyan-500 to-blue-600 hover:opacity-90">
              <IndianRupee className="w-4 h-4" /> Pay bill
            </Link>
            {card.can_edit_financials
              ? <Button variant="ghost" size="sm" onClick={() => setEditing(true)}><PencilLine className="w-3.5 h-3.5" /> Edit figures</Button>
              : <Button variant="ghost" size="sm" onClick={refresh} loading={busy} disabled={!card.can_refresh || card.verification_status !== "VERIFIED"}>
                  <RefreshCw className="w-3.5 h-3.5" /> Refresh from bank
                </Button>}
            <Button variant="ghost" size="sm" className="hover:!text-red-300" onClick={() => setRemoving(true)}><Trash2 className="w-3.5 h-3.5" /> Remove</Button>
          </div>
        </div>

        <div className="space-y-4">
          {card.card_source === "USER_ENTERED" && (
            <Banner tone="warn" icon={Info}>These figures were entered by you and have not been verified with {card.issuer_name}. Keep them up to date with “Edit figures”.</Banner>
          )}
          {card.is_stale && <Banner tone="warn">This data is more than a day old. Refresh to get your bank's latest figures.</Banner>}
          {["CONSENT_EXPIRED", "CONSENT_REVOKED"].includes(card.verification_status) && (
            <Banner tone="error">Data-sharing consent is no longer active, so these are the last verified figures (as of {fmtDateTime(card.data_as_of)}). Remove and re-link the card to resume updates.</Banner>
          )}

          <section className="bg-[#0C1220] border border-white/5 rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-white">Overview</h2>
              <Pill className={st.cls}>{st.label}</Pill>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <Fig label="Total credit limit" value={fmtINR(card.credit_limit)} />
              <Fig label="Outstanding balance" value={fmtINR(card.outstanding_balance)} strong />
              <Fig label="Available credit" value={fmtINR(card.available_credit)}
                note={card.available_credit_basis === "REPORTED" ? (card.card_source === "PROVIDER" ? "Reported by bank" : "As you entered")
                  : card.available_credit_basis === "ESTIMATED" ? "Estimate: limit − outstanding" : "Not available"} />
              <Fig label="Minimum due" value={fmtINR(card.minimum_amount_due)} />
              <Fig label="Payment due date" value={fmtDate(card.due_date)} />
              <Fig label="Billing cycle" value={card.billing_day ? `${card.billing_day}${ordinal(card.billing_day)} of month` : card.statement_date ? `Statement ${fmtDate(card.statement_date)}` : "—"} />
            </div>
            <div className="mt-5"><UtilizationBar pct={card.utilization_pct} /></div>
            {card.over_limit && <p className="text-xs text-red-300 mt-2">Outstanding exceeds the credit limit.</p>}
            {card.available_credit_basis === "ESTIMATED" && (
              <p className="text-[11px] text-gray-500 mt-3">Estimated available credit may differ from your bank's figure because of pending transactions, holds, refunds, fees or issuer rules.</p>
            )}
            <p className="text-[11px] text-gray-600 mt-3">Source: {card.source_label} · {card.card_source === "USER_ENTERED" ? "entered" : "as of"} {fmtDateTime(card.data_as_of)}</p>
          </section>

          <section className="bg-[#0C1220] border border-white/5 rounded-2xl overflow-hidden">
            <h2 className="px-5 py-3.5 border-b border-white/5 text-sm font-semibold text-white flex items-center gap-2"><ReceiptText className="w-4 h-4 text-cyan-300" /> Payment history</h2>
            {payments.length === 0 ? <p className="px-5 py-6 text-sm text-gray-500">No payments made through CardVault yet.</p> : (
              <ul className="divide-y divide-white/5">
                {payments.map((p) => (
                  <li key={p.payment_id} className="px-5 py-3 flex items-center justify-between gap-3 text-sm">
                    <div className="min-w-0">
                      <div className="text-white">{fmtINR(p.amount)}</div>
                      <div className="text-[11px] text-gray-500 font-mono truncate">{p.receipt_number} · {fmtDateTime(p.created_at)}</div>
                    </div>
                    <Pill className={(PAYMENT_STATUS[p.status] || PAYMENT_STATUS.CREATED).cls}>{(PAYMENT_STATUS[p.status] || PAYMENT_STATUS.CREATED).label}</Pill>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="bg-[#0C1220] border border-white/5 rounded-2xl overflow-hidden">
            <h2 className="px-5 py-3.5 border-b border-white/5 text-sm font-semibold text-white">Transactions</h2>
            {!txns?.available ? (
              <p className="px-5 py-6 text-sm text-gray-500">{txns?.message || "Transaction history is only available for bank-linked cards."}</p>
            ) : txns.transactions.length === 0 ? <p className="px-5 py-6 text-sm text-gray-500">No transactions shared by your bank yet.</p> : (
              <ul className="divide-y divide-white/5">
                {txns.transactions.map((t, i) => (
                  <li key={i} className="px-5 py-3 flex items-center justify-between gap-3 text-sm">
                    <div className="min-w-0"><div className="text-gray-200 truncate">{t.description || "Transaction"}</div><div className="text-[11px] text-gray-500">{fmtDate(t.date)}{t.status === "PENDING" ? " · pending" : ""}</div></div>
                    <span className={t.type === "CREDIT" ? "text-emerald-300" : "text-white"}>{t.type === "CREDIT" ? "+" : "−"}{fmtINR(t.amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {summary?.history?.length > 0 && (
            <section className="bg-[#0C1220] border border-white/5 rounded-2xl overflow-hidden">
              <h2 className="px-5 py-3.5 border-b border-white/5 text-sm font-semibold text-white flex items-center gap-2"><History className="w-4 h-4 text-cyan-300" /> Data history</h2>
              <ul className="divide-y divide-white/5 text-xs">
                {summary.history.map((h, i) => (
                  <li key={i} className="px-5 py-2.5 flex items-center justify-between gap-3">
                    <span className="text-gray-400">{fmtDateTime(h.captured_at)} · {h.source === "USER_ENTERED" ? "you" : "bank"}</span>
                    <span className="text-gray-300">Limit {fmtINR(h.credit_limit)} · Due {fmtINR(h.outstanding_balance)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>

      <AnimatePresence>
        {editing && (
          <ModalShell title="Edit card" subtitle={`${card.issuer_name} •••• ${card.last_four_digits}`} onClose={() => setEditing(false)}>
            <ManualCardForm card={card} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); load(); }} />
          </ModalShell>
        )}
        {removing && (
          <ConfirmDialog danger busy={busy} title="Remove this card?" confirmLabel="Remove card"
            message={`${card.card_nickname} (•••• ${card.last_four_digits}) and its stored figures will be deleted.${card.card_source === "PROVIDER" ? " Data-sharing consent will be revoked." : ""} Payment records are kept for your reference.`}
            onConfirm={remove} onClose={() => setRemoving(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}

function Fig({ label, value, note, strong }) {
  return (
    <div>
      <div className="text-[11px] text-gray-500">{label}</div>
      <div className={strong ? "text-white font-semibold" : "text-gray-200"}>{value}</div>
      {note && <div className="text-[10px] text-gray-600 mt-0.5">{note}</div>}
    </div>
  );
}

const ordinal = (n) => (n % 10 === 1 && n !== 11 ? "st" : n % 10 === 2 && n !== 12 ? "nd" : n % 10 === 3 && n !== 13 ? "rd" : "th");
