import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { AnimatePresence } from "motion/react";
import { Loader2, Plus } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useCards } from "../../hooks/useCards";
import { AddCreditCard } from "../../components/cards/AddCreditCard";
import { CreditCardList } from "../../components/cards/CreditCardList";
import { CreditCardSummary } from "../../components/cards/CreditCardSummary";
import { Banner, Button, useToast } from "../../components/ui";

export function UserCards() {
  const { api } = useAuth();
  const toast = useToast();
  const { cards, summary, loading, error, reload } = useCards();
  const [adding, setAdding] = useState(false);
  const [params, setParams] = useSearchParams();
  const [linking, setLinking] = useState(null);
  const handled = useRef(false);
  const pollTimer = useRef(null);
  useEffect(() => () => clearTimeout(pollTimer.current), []);

  // Returning from the provider: ?link_session=<id> (or ?link_error=...). Poll its status.
  useEffect(() => {
    if (handled.current) return;
    const sid = params.get("link_session");
    const lerr = params.get("link_error");
    if (!sid && !lerr) return;
    handled.current = true;
    setParams({}, { replace: true });
    if (lerr) { toast("error", "That linking link was invalid or already used. Please start again."); return; }
    let tries = 0;
    setLinking("Checking your bank link…");
    const check = async () => {
      const r = await api(`/cards/link-status/${encodeURIComponent(sid)}`);
      if (!r.ok) { setLinking(null); toast("error", r.message); return; }
      const s = r.data.status;
      if (s === "COMPLETED") { setLinking(null); toast("success", `${r.data.cards_linked} card(s) linked and verified.`); reload(); }
      else if (s === "FAILED" || s === "EXPIRED") { setLinking(null); toast("error", r.data.error_message || "Linking did not complete."); }
      else if (++tries < 20) pollTimer.current = setTimeout(check, 3000);
      else { setLinking(null); toast("info", "Still waiting for your bank. We'll show the card once it's ready."); }
    };
    check();
  }, [params, setParams, api, toast, reload]);

  return (
    <div className="p-4 lg:p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Credit cards</h1>
          <p className="text-sm text-gray-500">Limits, balances and dues for every card you've added.</p>
        </div>
        <Button onClick={() => setAdding(true)} className="shrink-0"><Plus className="w-4 h-4" /> <span className="hidden sm:inline">Add card</span></Button>
      </div>
      {linking && <Banner icon={Loader2}>{linking}</Banner>}
      {error && <Banner tone="error" action={<button onClick={reload} className="text-xs underline">Retry</button>}>{error}</Banner>}
      <CreditCardSummary summary={summary} loading={loading} />
      <CreditCardList cards={cards} loading={loading} onAdd={() => setAdding(true)} onChanged={reload} />
      <AnimatePresence>{adding && <AddCreditCard onClose={() => setAdding(false)} onAdded={reload} />}</AnimatePresence>
    </div>
  );
}
