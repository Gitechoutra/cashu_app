import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { BadgeCheck, ChevronRight, Link2, PencilLine, Search } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, ModalShell, Skeleton, inputCls } from "../ui";
import { BankLogo } from "../BankLogo";
import { LinkCreditCard } from "./LinkCreditCard";
import { ManualCardForm } from "./ManualCardForm";

/** Add-card flow: pick bank → choose Manual or Secure Linking → form / consent. */
export function AddCreditCard({ onClose, onAdded }) {
  const { api } = useAuth();
  const [step, setStep] = useState("bank");
  const [issuers, setIssuers] = useState([]);
  const [linkConfig, setLinkConfig] = useState(null);
  const [loadErr, setLoadErr] = useState("");
  const [issuer, setIssuer] = useState(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    let live = true;
    (async () => {
      const [i, l] = await Promise.all([api("/cards/issuers"), api("/cards/link/config")]);
      if (!live) return;
      if (i.ok) setIssuers(i.data.issuers); else setLoadErr(i.message);
      setLinkConfig(l.ok ? l.data : { configured: false });
    })();
    return () => { live = false; };
  }, [api]);

  const query = q.trim().toLowerCase();
  const popular = useMemo(() => issuers.filter((i) => i.popular), [issuers]);
  // Alphabetical, with "Other bank" pinned last; search matches full or short name.
  const listed = useMemo(() => {
    const match = (i) => !query || i.name.toLowerCase().includes(query) || i.short_name.toLowerCase().includes(query);
    const byName = (a, b) => a.name.localeCompare(b.name);
    const rows = issuers.filter(match);
    return [...rows.filter((i) => i.code !== "OTHER").sort(byName), ...rows.filter((i) => i.code === "OTHER")];
  }, [issuers, query]);
  const pick = (i) => { setIssuer(i); setStep("method"); };

  const titles = {
    bank: ["Add a credit card", "Select your card's issuing bank"],
    method: [issuer?.name, "How would you like to add this card?"],
    manual: ["Add card manually", issuer?.name],
    link: ["Secure card linking", issuer?.name],
  };

  return (
    <ModalShell title={titles[step][0]} subtitle={titles[step][1]} onClose={onClose}>
      <AnimatePresence mode="wait">
        <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.15 }}>
          {step === "bank" && (
            <div>
              <div className="relative mb-5">
                <Search className="w-4 h-4 text-gray-500 absolute left-4 top-1/2 -translate-y-1/2" />
                <input className={`${inputCls()} pl-11 rounded-full`} placeholder="Search by bank name" value={q}
                  onChange={(e) => setQ(e.target.value)} autoFocus aria-label="Search by bank name" />
              </div>
              {loadErr && <Banner tone="error">{loadErr}</Banner>}

              {issuers.length === 0 && !loadErr && (
                <div className="grid grid-cols-3 gap-y-6 py-2">
                  {[0, 1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="flex flex-col items-center gap-2"><Skeleton className="w-16 h-16 !rounded-full" /><Skeleton className="w-20 h-3" /></div>
                  ))}
                </div>
              )}

              {/* Popular banks — circular grid (hidden while searching) */}
              {!query && popular.length > 0 && (
                <div className="grid grid-cols-3 gap-x-2 gap-y-5 pb-6 border-b border-white/5">
                  {popular.map((i) => (
                    <button key={i.issuer_id} onClick={() => pick(i)}
                      className="group flex flex-col items-center gap-2 rounded-2xl py-2 px-1 hover:bg-white/[0.03] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/40 transition-colors">
                      <BankLogo code={i.code} name={i.name} size="lg" className="group-hover:ring-cyan-400/50 transition-shadow" />
                      <span className="text-xs sm:text-sm text-gray-300 group-hover:text-white text-center leading-tight line-clamp-2">{i.name}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* All banks — alphabetical list */}
              {listed.length > 0 && (
                <div className={query ? "" : "pt-5"}>
                  <div className="text-[11px] font-semibold tracking-[0.18em] text-gray-500 mb-2 px-1">{query ? "RESULTS" : "ALL BANKS"}</div>
                  <ul className="-mx-1">
                    {listed.map((i) => (
                      <li key={i.issuer_id}>
                        <button onClick={() => pick(i)}
                          className="w-full flex items-center gap-4 px-2 py-2.5 rounded-xl text-left hover:bg-white/[0.04] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/40 transition-colors">
                          <BankLogo code={i.code} name={i.name} size="md" />
                          <span className="flex-1 min-w-0 text-sm text-gray-200 truncate">{i.name}</span>
                          {i.linkable && <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-emerald-500/30 text-emerald-300">Linkable</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {issuers.length > 0 && listed.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-6">No bank matches “{q}”. Choose “Other bank” to add it manually.</p>
              )}
            </div>
          )}

          {step === "method" && issuer && (
            <div className="space-y-3">
              <div className="flex items-center gap-3 pb-1">
                <BankLogo code={issuer.code} name={issuer.name} size="lg" />
                <div className="text-sm text-gray-300">{issuer.name}</div>
              </div>
              <MethodCard icon={PencilLine} title="Manual entry" badge="Available now"
                text="Enter your card's last 4 digits, limit, balance and due date yourself. Shown as User-entered — Not Bank Verified."
                onClick={() => setStep("manual")} />
              <MethodCard icon={Link2} title="Secure card linking"
                badge={!linkConfig ? "Checking…" : !linkConfig.configured ? "Not configured" : issuer.linkable ? "Bank verified" : "Not supported for this bank"}
                badgeTone={linkConfig?.configured && issuer.linkable ? "ok" : "muted"}
                text="Approve read-only access through an authorised financial-data provider. Your limit and balance come from the bank."
                onClick={() => setStep("link")} />
              <button onClick={() => setStep("bank")} className="text-xs text-gray-500 hover:text-white">← Change bank</button>
            </div>
          )}

          {step === "manual" && (
            <ManualCardForm issuer={issuer} onCancel={() => setStep("method")} onSaved={(c) => { onAdded(c); onClose(); }} />
          )}

          {step === "link" && (
            <LinkCreditCard issuer={issuer} linkConfig={linkConfig} onBack={() => setStep("method")} onManual={() => setStep("manual")} />
          )}
        </motion.div>
      </AnimatePresence>
    </ModalShell>
  );
}

function MethodCard({ icon: Icon, title, text, badge, badgeTone = "ok", onClick }) {
  return (
    <button onClick={onClick}
      className="w-full text-left flex items-start gap-3 rounded-2xl border border-white/8 bg-[#141C30]/60 hover:border-cyan-500/40 p-4 transition-colors">
      <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-cyan-300" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-white">{title}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${badgeTone === "ok"
            ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10" : "text-gray-400 border-white/10 bg-white/5"}`}>
            {badgeTone === "ok" && title.startsWith("Secure") && <BadgeCheck className="inline w-3 h-3 mr-0.5" />}{badge}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-1 leading-relaxed">{text}</p>
      </div>
      <ChevronRight className="w-4 h-4 text-gray-600 mt-3" />
    </button>
  );
}
