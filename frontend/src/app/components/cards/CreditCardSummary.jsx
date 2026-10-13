import { CalendarClock, Gauge, Landmark, Wallet } from "lucide-react";
import { daysUntil, fmtDate, fmtINR } from "../../utils/format";
import { Skeleton } from "../ui";

/** Portfolio tiles. Totals only include cards with both limit and balance known,
 *  and say so when some were left out. */
export function CreditCardSummary({ summary, loading }) {
  if (loading && !summary) {
    return <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}</div>;
  }
  if (!summary || summary.cards_count === 0) return null;
  const util = summary.overall_utilization_pct === null ? null : Number(summary.overall_utilization_pct);
  const nd = summary.next_due;
  const days = nd ? daysUntil(nd.due_date) : null;
  const tiles = [
    { label: "Total credit limit", value: fmtINR(summary.total_credit_limit, { compact: true }), icon: Landmark, accent: "text-cyan-300" },
    { label: "Total outstanding", value: fmtINR(summary.total_outstanding, { compact: true }), icon: Wallet, accent: "text-white" },
    { label: "Overall utilisation", value: util === null ? "—" : `${util.toFixed(1)}%`, icon: Gauge,
      accent: util === null ? "text-gray-400" : util >= 30 ? "text-amber-300" : "text-emerald-300" },
    { label: "Next due", value: nd ? fmtDate(nd.due_date) : "No dues", icon: CalendarClock,
      accent: days !== null && days < 0 ? "text-red-300" : days !== null && days <= 5 ? "text-amber-300" : "text-white",
      sub: nd ? `${nd.card_nickname} · ${fmtINR(nd.outstanding_balance)}` : null },
  ];
  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {tiles.map((t) => (
          <div key={t.label} className="bg-[#0C1220] border border-white/5 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-500">{t.label}</span>
              <t.icon className={`w-4 h-4 ${t.accent}`} />
            </div>
            <div className={`text-lg sm:text-xl font-bold ${t.accent}`}>{t.value}</div>
            {t.sub && <div className="text-[11px] text-gray-500 mt-0.5 truncate">{t.sub}</div>}
          </div>
        ))}
      </div>
      {summary.cards_in_totals < summary.cards_count && (
        <p className="text-[11px] text-gray-600 mt-2">
          Totals include {summary.cards_in_totals} of {summary.cards_count} cards — the rest are missing a limit or balance.
        </p>
      )}
    </div>
  );
}
