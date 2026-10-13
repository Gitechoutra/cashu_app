import { useState } from "react";
import { Link } from "react-router";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, CalendarClock, CreditCard, IndianRupee, Plus, RefreshCw } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useCards } from "../../hooks/useCards";
import { AddCreditCard } from "../../components/cards/AddCreditCard";
import { CreditCardSummary } from "../../components/cards/CreditCardSummary";
import { CreditCardVisual } from "../../components/cards/CreditCardItem";
import { CardVerificationStatus } from "../../components/cards/CardVerificationStatus";
import { Banner, Button, Pill, Skeleton } from "../../components/ui";
import { BankLogo } from "../../components/BankLogo";
import { BILL_STATUS, daysUntil, fmtDate, fmtINR } from "../../utils/format";

/** Home dashboard: greeting, portfolio summary, Add Credit Card, cards and upcoming dues. */
export function UserHome() {
  const { user } = useAuth();
  const { cards, summary, loading, error, reload } = useCards();
  const [adding, setAdding] = useState(false);
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const dues = cards.filter((c) => c.due_date && Number(c.outstanding_balance) > 0)
    .sort((a, b) => a.due_date.localeCompare(b.due_date)).slice(0, 4);

  return (
    <div className="p-4 lg:p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-gray-500">{greet},</p>
          <h1 className="text-2xl font-bold text-white">{user?.full_name?.split(" ")[0] || "there"}</h1>
        </div>
        <button onClick={reload} aria-label="Refresh" className="p-2 rounded-xl bg-white/5 border border-white/10 text-gray-400 hover:text-white">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {error && <Banner tone="error" action={<button onClick={reload} className="text-xs underline">Retry</button>}>{error}</Banner>}

      {/* Add Credit Card hero */}
      <motion.button onClick={() => setAdding(true)} whileHover={{ y: -2 }} whileTap={{ scale: 0.99 }}
        className="w-full text-left relative overflow-hidden rounded-3xl p-5 sm:p-6 border border-cyan-500/20 bg-gradient-to-br from-cyan-500/15 via-blue-600/10 to-transparent">
        <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full bg-cyan-400/10 blur-2xl" />
        <div className="relative flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 shrink-0">
            <Plus className="w-6 h-6 text-white" />
          </div>
          <div className="flex-1">
            <div className="text-base font-semibold text-white">Add Credit Card</div>
            <div className="text-sm text-gray-400">Add manually in under a minute, or link securely through your bank.</div>
          </div>
          <ArrowRight className="w-5 h-5 text-cyan-300 hidden sm:block" />
        </div>
      </motion.button>

      <CreditCardSummary summary={summary} loading={loading} />

      {/* Cards strip */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-white">Your cards</h2>
          {cards.length > 0 && <Link to="/user/cards" className="text-xs text-cyan-300 hover:text-cyan-200 flex items-center gap-1">View all <ArrowRight className="w-3 h-3" /></Link>}
        </div>
        {loading && cards.length === 0 ? (
          <div className="flex gap-4"><Skeleton className="w-72 h-44" /><Skeleton className="w-72 h-44 hidden sm:block" /></div>
        ) : cards.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center">
            <CreditCard className="w-8 h-8 text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-gray-400">No cards yet.</p>
            <Button className="mt-4" size="sm" onClick={() => setAdding(true)}><Plus className="w-4 h-4" /> Add your first card</Button>
          </div>
        ) : (
          <div className="flex gap-4 overflow-x-auto no-scrollbar snap-x pb-1 -mx-4 px-4 lg:mx-0 lg:px-0">
            {cards.map((c) => (
              <Link key={c.card_id} to={`/user/cards/${c.card_id}`} className="snap-start shrink-0 w-72 sm:w-80 space-y-2">
                <CreditCardVisual card={c} />
                <div className="flex items-center justify-between px-1">
                  <CardVerificationStatus card={c} compact />
                  <span className="text-xs text-gray-400">{fmtINR(c.outstanding_balance)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Upcoming dues */}
      {dues.length > 0 && (
        <section className="bg-[#0C1220] border border-white/5 rounded-2xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-white/5 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2"><CalendarClock className="w-4 h-4 text-cyan-300" /> Upcoming dues</h2>
            <Link to="/user/bills" className="text-xs text-cyan-300">Pay bills</Link>
          </div>
          <ul className="divide-y divide-white/5">
            {dues.map((c) => {
              const d = daysUntil(c.due_date);
              const st = BILL_STATUS[c.bill_status] || BILL_STATUS.UNKNOWN;
              return (
                <li key={c.card_id} className="flex items-center gap-3 px-5 py-3.5">
                  <BankLogo code={c.issuer_code} name={c.issuer_name} gradient={c.gradient} size="sm" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">{c.card_nickname} <span className="text-gray-500">•• {c.last_four_digits}</span></div>
                    <div className="text-xs text-gray-500">{fmtDate(c.due_date)} · {d < 0 ? `${-d} day(s) overdue` : d === 0 ? "due today" : `in ${d} day(s)`}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold text-white">{fmtINR(c.outstanding_balance)}</div>
                    <Pill className={st.cls}>{st.label}</Pill>
                  </div>
                  <Link to={`/user/bills?card=${c.card_id}`} aria-label="Pay" className="p-2 rounded-lg bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20"><IndianRupee className="w-4 h-4" /></Link>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <AnimatePresence>{adding && <AddCreditCard onClose={() => setAdding(false)} onAdded={reload} />}</AnimatePresence>
    </div>
  );
}
