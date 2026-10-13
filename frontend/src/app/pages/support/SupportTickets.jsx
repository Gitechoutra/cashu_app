import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, CreditCard, Inbox, RefreshCw, Search, UserCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Button, EmptyState, Pill, Skeleton, inputCls, useToast } from "../../components/ui";
import { PRIORITY, TICKET_STATUS, TicketThread } from "../../components/TicketThread";
import { BILL_STATUS, PAYMENT_STATUS, fmtDate, fmtDateTime, fmtINR, timeAgo } from "../../utils/format";

const FILTERS = [["ACTIVE", "Active"], ["OPEN", "Open"], ["IN_PROGRESS", "In progress"], ["WAITING_ON_USER", "Awaiting reply"], ["RESOLVED", "Resolved"], ["CLOSED", "Closed"]];

/** Ticket queue + conversation + masked customer context (Customer Support / Admin). */
export function SupportTickets() {
  const { api } = useAuth();
  const toast = useToast();
  const [filter, setFilter] = useState("ACTIVE");
  const [mine, setMine] = useState(false);
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null);       // { ticket, customer, cards, recent_payments }
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ status: filter, per_page: "50", ...(mine ? { mine: "true" } : {}), ...(q.trim() ? { q: q.trim() } : {}) });
    const r = await api(`/support/tickets?${params}`);
    if (r.ok) setData(r.data); else toast("error", r.message);
  }, [api, filter, mine, q, toast]);
  useEffect(() => { load(); }, [filter, mine]); // eslint-disable-line react-hooks/exhaustive-deps

  const open = useCallback(async (id) => {
    const r = await api(`/support/tickets/${id}`);
    if (r.ok) setSel(r.data); else toast("error", r.message);
  }, [api, toast]);

  useEffect(() => {
    if (!sel) return;
    const t = setInterval(() => open(sel.ticket.ticket_id), 15000);
    return () => clearInterval(t);
  }, [sel, open]);

  const update = async (body) => {
    setBusy(true);
    const r = await api(`/support/tickets/${sel.ticket.ticket_id}`, { method: "PATCH", body });
    setBusy(false);
    if (r.ok) { setSel((s) => ({ ...s, ticket: r.data.ticket })); load(); } else toast("error", r.message);
  };

  const send = async (message, internal) => {
    const r = await api(`/support/tickets/${sel.ticket.ticket_id}/messages`, { method: "POST", body: { message, internal } });
    if (r.ok) { setSel((s) => ({ ...s, ticket: r.data.ticket })); load(); return true; }
    toast("error", r.message);
    return false;
  };

  return (
    <div className="p-4 lg:p-6 max-w-7xl mx-auto">
      <div className={`grid gap-5 ${sel ? "lg:grid-cols-[360px_1fr]" : ""}`}>
        {/* Queue */}
        <section className={`${sel ? "hidden lg:block" : ""} space-y-3`}>
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold text-white flex items-center gap-2"><Inbox className="w-5 h-5 text-violet-300" /> Tickets</h1>
            <button onClick={load} aria-label="Refresh" className="p-2 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white"><RefreshCw className="w-4 h-4" /></button>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); load(); }} className="relative">
            <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input className={`${inputCls()} pl-10`} placeholder="Reference (CV-…) or subject" value={q} onChange={(e) => setQ(e.target.value)} />
          </form>
          <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
            {FILTERS.map(([v, l]) => (
              <button key={v} onClick={() => setFilter(v)}
                className={`shrink-0 text-xs px-3 py-1.5 rounded-full border ${filter === v ? "border-violet-500/40 bg-violet-500/10 text-violet-200" : "border-white/10 text-gray-400 hover:text-white"}`}>
                {l}{data?.counts && v !== "ACTIVE" ? ` · ${data.counts[v] ?? 0}` : ""}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-400"><input type="checkbox" className="accent-violet-500" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Assigned to me</label>

          {data === null ? <Skeleton className="h-64" /> : data.items.length === 0 ? (
            <EmptyState icon={Inbox} title="Queue is clear" text="No tickets match this filter." />
          ) : (
            <ul className="bg-[#0C1220] border border-white/5 rounded-2xl divide-y divide-white/5 overflow-hidden">
              {data.items.map((t) => {
                const st = TICKET_STATUS[t.status] || TICKET_STATUS.OPEN;
                return (
                  <li key={t.ticket_id}>
                    <button onClick={() => open(t.ticket_id)}
                      className={`w-full text-left px-4 py-3.5 hover:bg-white/[0.03] ${sel?.ticket.ticket_id === t.ticket_id ? "bg-violet-500/[0.06]" : ""}`}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[11px] font-mono text-gray-500">{t.reference}</span>
                        <span className={`text-[10px] font-semibold ${PRIORITY[t.priority]}`}>{t.priority}</span>
                      </div>
                      <div className="text-sm text-white truncate mt-0.5">{t.subject}</div>
                      <div className="text-xs text-gray-500 truncate">{t.customer.full_name || "Customer"} · {t.last_message}</div>
                      <div className="flex items-center justify-between mt-2">
                        <Pill className={st.cls}>{st.label}</Pill>
                        <span className="text-[11px] text-gray-600">{timeAgo(t.updated_at)}</span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* Conversation + context */}
        {sel && (
          <section className="space-y-4 min-w-0">
            <button onClick={() => setSel(null)} className="lg:hidden text-xs text-gray-500 hover:text-white inline-flex items-center gap-1"><ArrowLeft className="w-3.5 h-3.5" /> Queue</button>
            <div className="grid xl:grid-cols-[1fr_300px] gap-4">
              <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-5 min-w-0">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[11px] font-mono text-gray-500">{sel.ticket.reference} · {sel.ticket.category}</div>
                    <h2 className="text-lg font-semibold text-white break-words">{sel.ticket.subject}</h2>
                    <div className="text-xs text-gray-500">Opened {fmtDateTime(sel.ticket.created_at)}{sel.ticket.assignee ? ` · assigned to ${sel.ticket.assignee}` : " · unassigned"}</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!sel.ticket.assignee && <Button size="sm" variant="ghost" loading={busy} onClick={() => update({ assign_to_me: true })}><UserCheck className="w-3.5 h-3.5" /> Assign to me</Button>}
                    <select value={sel.ticket.status} onChange={(e) => update({ status: e.target.value })} disabled={busy}
                      className="text-xs rounded-lg bg-[#141C30] border border-white/10 px-2 py-2 text-gray-200">
                      {Object.entries(TICKET_STATUS).map(([v, s]) => <option key={v} value={v}>{s.label}</option>)}
                    </select>
                    <select value={sel.ticket.priority} onChange={(e) => update({ priority: e.target.value })} disabled={busy}
                      className="text-xs rounded-lg bg-[#141C30] border border-white/10 px-2 py-2 text-gray-200">
                      {Object.keys(PRIORITY).map((p) => <option key={p} value={p}>{p}</option>)}
                    </select>
                  </div>
                </div>
                <div className="mt-5">
                  <TicketThread messages={sel.ticket.messages} viewer="SUPPORT" onSend={send} />
                </div>
              </div>

              <aside className="space-y-4">
                <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-4 text-sm">
                  <div className="text-xs text-gray-500 mb-2">Customer</div>
                  <div className="text-white font-medium">{sel.customer.full_name || "—"}</div>
                  <div className="text-gray-400 text-xs">{sel.customer.mobile_number} · {sel.customer.status}</div>
                  <div className="text-gray-600 text-[11px] mt-1">Member since {fmtDate(sel.customer.member_since)}</div>
                </div>
                <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-4">
                  <div className="text-xs text-gray-500 mb-2 flex items-center gap-1.5"><CreditCard className="w-3.5 h-3.5" /> Cards ({sel.cards.length})</div>
                  {sel.cards.length === 0 ? <p className="text-xs text-gray-600">No cards.</p> : sel.cards.map((c, i) => (
                    <div key={i} className="py-1.5 text-xs">
                      <div className="text-gray-200">{c.issuer_name} · {c.card_nickname} {c.masked_number}</div>
                      <div className="text-gray-500">{c.source === "USER_ENTERED" ? "User-entered" : c.verification_status} · due {fmtDate(c.due_date)} · {(BILL_STATUS[c.bill_status] || BILL_STATUS.UNKNOWN).label}</div>
                    </div>
                  ))}
                </div>
                <div className="bg-[#0C1220] border border-white/5 rounded-2xl p-4">
                  <div className="text-xs text-gray-500 mb-2">Recent payments</div>
                  {sel.recent_payments.length === 0 ? <p className="text-xs text-gray-600">None.</p> : sel.recent_payments.map((p) => (
                    <div key={p.payment_id} className="py-1.5 flex items-center justify-between gap-2 text-xs">
                      <div className="min-w-0"><div className="text-gray-200">{fmtINR(p.amount)}</div><div className="text-gray-500 font-mono truncate">{p.receipt_number}</div></div>
                      <Pill className={(PAYMENT_STATUS[p.status] || PAYMENT_STATUS.CREATED).cls}>{(PAYMENT_STATUS[p.status] || PAYMENT_STATUS.CREATED).label}</Pill>
                    </div>
                  ))}
                </div>
                <Banner>Read-only, masked view. Never ask customers for their PIN, OTP, CVV or full card number.</Banner>
              </aside>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
