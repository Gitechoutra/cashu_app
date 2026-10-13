import { useCallback, useEffect, useState } from "react";
import { AnimatePresence } from "motion/react";
import { ArrowLeft, Headset, MessageSquarePlus, RefreshCw } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Button, EmptyState, Field, ModalShell, Pill, Skeleton, inputCls, useToast } from "../../components/ui";
import { TICKET_STATUS, TicketThread } from "../../components/TicketThread";
import { fmtDateTime } from "../../utils/format";
import { usePlatformSettings } from "../../hooks/usePlatform";

const CATEGORIES = [
  ["CARD", "A card in my account"], ["PAYMENT", "A bill payment"], ["ACCOUNT", "My account / sign-in"],
  ["SECURITY", "Security concern"], ["OTHER", "Something else"],
];

/** Customer help desk: raise tickets and chat with Customer Support. */
export function HelpSupport() {
  const { api } = useAuth();
  const toast = useToast();
  const [tickets, setTickets] = useState(null);
  const [open, setOpen] = useState(null);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState("");
  const platform = usePlatformSettings();

  const load = useCallback(async () => {
    const r = await api("/tickets?per_page=50");
    if (r.ok) setTickets(r.data.items); else setErr(r.message);
  }, [api]);
  useEffect(() => { load(); }, [load]);

  const openTicket = useCallback(async (id) => {
    const r = await api(`/tickets/${id}`);
    if (r.ok) setOpen(r.data.ticket); else toast("error", r.message);
  }, [api, toast]);

  // Light polling so support replies show up while the conversation is open.
  useEffect(() => {
    if (!open) return;
    const t = setInterval(() => openTicket(open.ticket_id), 15000);
    return () => clearInterval(t);
  }, [open, openTicket]);

  const reply = async (body) => {
    const r = await api(`/tickets/${open.ticket_id}/messages`, { method: "POST", body: { message: body } });
    if (r.ok) { setOpen(r.data.ticket); load(); return true; }
    toast("error", r.message);
    return false;
  };

  if (open) {
    const st = TICKET_STATUS[open.status] || TICKET_STATUS.OPEN;
    return (
      <div className="p-4 lg:p-8 max-w-3xl mx-auto space-y-4">
        <button onClick={() => setOpen(null)} className="text-xs text-gray-500 hover:text-white inline-flex items-center gap-1"><ArrowLeft className="w-3.5 h-3.5" /> All tickets</button>
        <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[11px] text-gray-500 font-mono">{open.reference}</div>
              <h1 className="text-lg font-semibold text-white break-words">{open.subject}</h1>
              <div className="text-xs text-gray-500 mt-0.5">
                Opened {fmtDateTime(open.created_at)}{open.assignee ? ` · with ${open.assignee}` : ""}
                {open.card ? ` · ${open.card.card_nickname} ${open.card.masked_number}` : ""}
              </div>
            </div>
            <Pill className={st.cls}>{st.label}</Pill>
          </div>
          <div className="mt-5">
            <TicketThread messages={open.messages} viewer="CUSTOMER" onSend={reply}
              disabled={open.status === "CLOSED"} disabledReason="This ticket is closed. Raise a new one if you still need help." />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-8 max-w-3xl mx-auto space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2"><Headset className="w-5 h-5 text-cyan-300" /> Help & Support</h1>
          <p className="text-sm text-gray-500">Chat with our Customer Support team.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} aria-label="Refresh" className="p-2.5 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white"><RefreshCw className="w-4 h-4" /></button>
          <Button onClick={() => setCreating(true)}><MessageSquarePlus className="w-4 h-4" /> <span className="hidden sm:inline">New ticket</span></Button>
        </div>
      </div>
      <Banner>
        {platform.SUPPORT_HOURS ? <>Support hours: <b>{platform.SUPPORT_HOURS}</b>. </> : null}
        {platform.SUPPORT_EMAIL ? <>Email: <b>{platform.SUPPORT_EMAIL}</b>. </> : null}
        Support will never ask for your PIN, OTP, CVV or full card number.
      </Banner>
      {err && <Banner tone="error">{err}</Banner>}
      {tickets === null ? <Skeleton className="h-40" /> : tickets.length === 0 ? (
        <EmptyState icon={Headset} title="No tickets yet" text="Have a question about a card or payment? We're here to help."
          action={<Button onClick={() => setCreating(true)}><MessageSquarePlus className="w-4 h-4" /> Raise a ticket</Button>} />
      ) : (
        <ul className="bg-[#0C1220] border border-white/5 rounded-2xl divide-y divide-white/5 overflow-hidden">
          {tickets.map((t) => {
            const st = TICKET_STATUS[t.status] || TICKET_STATUS.OPEN;
            return (
              <li key={t.ticket_id}>
                <button onClick={() => openTicket(t.ticket_id)} className="w-full text-left px-5 py-4 hover:bg-white/[0.02] flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">{t.subject}</div>
                    <div className="text-[11px] text-gray-500"><span className="font-mono">{t.reference}</span> · updated {fmtDateTime(t.updated_at)}</div>
                  </div>
                  <Pill className={st.cls}>{st.label}</Pill>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <AnimatePresence>{creating && <NewTicket onClose={() => setCreating(false)} onCreated={(t) => { setCreating(false); load(); setOpen(t); }} />}</AnimatePresence>
    </div>
  );
}

function NewTicket({ onClose, onCreated }) {
  const { api } = useAuth();
  const toast = useToast();
  const [cards, setCards] = useState([]);
  const [f, setF] = useState({ category: "CARD", subject: "", message: "", card_id: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/cards").then((r) => r.ok && setCards(r.data.cards)); }, [api]);

  const submit = async (e) => {
    e.preventDefault();
    const er = {};
    if (f.subject.trim().length < 4) er.subject = "Add a short subject (at least 4 characters).";
    if (!f.message.trim()) er.message = "Describe the issue.";
    setErrors(er);
    if (Object.keys(er).length || busy) return;
    setBusy(true);
    const r = await api("/tickets", { method: "POST", body: { ...f, card_id: f.card_id || undefined } });
    setBusy(false);
    if (r.ok) { toast("success", `Ticket ${r.data.ticket.reference} created.`); onCreated(r.data.ticket); }
    else { setErrors(r.errors || {}); toast("error", r.message); }
  };

  return (
    <ModalShell title="New support ticket" onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        <Field label="What is it about?">
          <select className={inputCls()} value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
            {CATEGORIES.map(([v, l]) => <option key={v} value={v} className="bg-[#141C30]">{l}</option>)}
          </select>
        </Field>
        {f.category === "CARD" && cards.length > 0 && (
          <Field label="Card" optional>
            <select className={inputCls()} value={f.card_id} onChange={(e) => setF({ ...f, card_id: e.target.value })}>
              <option value="" className="bg-[#141C30]">Not about a specific card</option>
              {cards.map((c) => <option key={c.card_id} value={c.card_id} className="bg-[#141C30]">{c.issuer_name} · {c.card_nickname} •••• {c.last_four_digits}</option>)}
            </select>
          </Field>
        )}
        <Field label="Subject" error={errors.subject}>
          <input className={inputCls(errors.subject)} maxLength={120} value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })} placeholder="e.g. Payment shows pending" />
        </Field>
        <Field label="Message" error={errors.message} hint={`${f.message.length}/2000`}>
          <textarea rows={5} className={`${inputCls(errors.message)} resize-none`} maxLength={2000} value={f.message}
            onChange={(e) => setF({ ...f, message: e.target.value })} placeholder="Tell us what happened. Don't include your PIN, OTP, CVV or full card number." />
        </Field>
        <Button type="submit" className="w-full" loading={busy}>Submit ticket</Button>
      </form>
    </ModalShell>
  );
}
