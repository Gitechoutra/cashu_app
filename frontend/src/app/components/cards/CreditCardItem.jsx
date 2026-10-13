import { Link } from "react-router";
import { motion } from "motion/react";
import { ChevronRight, CreditCard, IndianRupee, Trash2, Wifi } from "lucide-react";
import { BILL_STATUS, fmtDate, fmtINR, utilColor } from "../../utils/format";
import { Pill } from "../ui";
import { CardVerificationStatus } from "./CardVerificationStatus";
import { BankLogo } from "../BankLogo";

const NETWORK_MARK = { VISA: "VISA", MASTERCARD: "mastercard", RUPAY: "RuPay", AMEX: "AMEX", DINERS: "Diners Club", OTHER: "" };

/** The physical-looking card face. Shows only the last 4 digits — ever. */
export function CreditCardVisual({ card, size = "md" }) {
  const [g1, g2] = card.gradient || ["#1E293B", "#0F172A"];
  const sm = size === "sm";
  return (
    <div className={`card-sheen relative overflow-hidden ${sm ? "rounded-xl p-3.5 aspect-[1.586]" : "rounded-2xl p-5 aspect-[1.586]"} text-white shadow-xl shadow-black/40 ring-1 ring-white/10 select-none`}
      style={{ background: `linear-gradient(135deg, ${g1} 0%, ${g2} 100%)` }}>
      <div className="absolute -right-10 -top-10 w-40 h-40 rounded-full bg-white/[0.06]" />
      <div className="absolute -right-4 bottom-[-60px] w-52 h-52 rounded-full bg-white/[0.04]" />
      <div className="relative h-full flex flex-col">
        <div className="flex items-start justify-between gap-2">
          <BankLogo code={card.issuer_code} name={card.issuer_name} gradient={card.gradient} size="sm" className="mr-2.5" />
          <div className="min-w-0 flex-1">
            <div className={`${sm ? "text-[10px]" : "text-xs"} uppercase tracking-[0.18em] text-white/70 truncate`}>{card.issuer_name}</div>
            <div className={`${sm ? "text-sm" : "text-base"} font-semibold truncate`}>{card.card_nickname}</div>
          </div>
          <Wifi className={`${sm ? "w-4 h-4" : "w-5 h-5"} rotate-90 text-white/60 shrink-0`} />
        </div>
        <div className={`${sm ? "mt-2 w-7 h-5" : "mt-4 w-10 h-7"} rounded-md bg-gradient-to-br from-amber-200 to-amber-400/80 ring-1 ring-black/10`} />
        <div className={`mt-auto font-mono tracking-[0.2em] ${sm ? "text-xs" : "text-base sm:text-lg"} text-white/90`}>
          {card.masked_number || `•••• •••• •••• ${card.last_four_digits}`}
        </div>
        <div className="flex items-end justify-between mt-1">
          <span className={`${sm ? "text-[9px]" : "text-[10px]"} text-white/60`}>
            {card.card_source === "USER_ENTERED" ? "User-entered" : card.card_source === "PROVIDER" ? "Bank-linked" : "Sample"}
          </span>
          <span className={`${sm ? "text-xs" : "text-sm"} font-bold italic tracking-wide text-white/90`}>{NETWORK_MARK[card.card_network] ?? ""}</span>
        </div>
      </div>
    </div>
  );
}

export function UtilizationBar({ pct }) {
  const n = pct === null || pct === undefined ? null : Number(pct);
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1.5">
        <span className="text-gray-500">Credit utilisation</span>
        <span className={n === null ? "text-gray-500" : n >= 50 ? "text-red-300" : n >= 30 ? "text-amber-300" : "text-emerald-300"}>
          {n === null ? "Not available" : `${n.toFixed(2)}%`}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
        <motion.div className={`h-full rounded-full ${utilColor(n)}`} initial={{ width: 0 }}
          animate={{ width: `${Math.min(n ?? 0, 100)}%` }} transition={{ duration: 0.7, ease: "easeOut" }} />
      </div>
    </div>
  );
}

/** Card + key figures + actions, used in the card list. */
export function CreditCardItem({ card, onRemove }) {
  const st = BILL_STATUS[card.bill_status] || BILL_STATUS.UNKNOWN;
  return (
    <motion.div layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}
      className="bg-[#0C1220] border border-white/5 rounded-2xl p-4 hover:border-cyan-500/20 transition-colors flex flex-col">
      <Link to={`/user/cards/${card.card_id}`} aria-label={`View ${card.card_nickname} details`}>
        <CreditCardVisual card={card} />
      </Link>

      <div className="mt-4 flex items-center justify-between gap-2">
        <CardVerificationStatus card={card} compact />
        <Pill className={st.cls}>{st.label}</Pill>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-3 mt-4 text-sm">
        <Stat label="Outstanding" value={fmtINR(card.outstanding_balance)} strong />
        <Stat label={card.available_credit_basis === "ESTIMATED" ? "Available (est.)" : "Available"} value={fmtINR(card.available_credit)} />
        <Stat label="Credit limit" value={fmtINR(card.credit_limit)} />
        <Stat label="Due date" value={fmtDate(card.due_date)} />
        {card.minimum_amount_due !== null && <Stat label="Minimum due" value={fmtINR(card.minimum_amount_due)} />}
      </dl>
      <div className="mt-4"><UtilizationBar pct={card.utilization_pct} /></div>

      <div className="mt-4 pt-4 border-t border-white/5 grid grid-cols-3 gap-2">
        <Link to={`/user/cards/${card.card_id}`} className="flex items-center justify-center gap-1 text-xs px-2 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-gray-200">
          Details <ChevronRight className="w-3.5 h-3.5" />
        </Link>
        <Link to={`/user/bills?card=${card.card_id}`} className="flex items-center justify-center gap-1 text-xs px-2 py-2 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-200 border border-cyan-500/20">
          <IndianRupee className="w-3.5 h-3.5" /> Pay bill
        </Link>
        <button onClick={() => onRemove(card)} className="flex items-center justify-center gap-1 text-xs px-2 py-2 rounded-lg text-gray-400 hover:text-red-300 hover:bg-red-500/10">
          <Trash2 className="w-3.5 h-3.5" /> Remove
        </button>
      </div>
    </motion.div>
  );
}

function Stat({ label, value, strong }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] text-gray-500">{label}</dt>
      <dd className={`truncate ${strong ? "text-white font-semibold" : "text-gray-200"}`}>{value}</dd>
    </div>
  );
}

export const CardIcon = CreditCard;
