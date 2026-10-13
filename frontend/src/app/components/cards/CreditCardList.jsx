import { useState } from "react";
import { AnimatePresence } from "motion/react";
import { CreditCard, Plus } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Button, ConfirmDialog, EmptyState, Skeleton, useToast } from "../ui";
import { CreditCardItem } from "./CreditCardItem";

export function CreditCardList({ cards, loading, onAdd, onChanged }) {
  const { api } = useAuth();
  const toast = useToast();
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);

  const confirmRemove = async () => {
    setBusy(true);
    const r = await api(`/cards/${removing.card_id}`, { method: "DELETE" });
    setBusy(false);
    if (r.ok) {
      toast("success", `${removing.card_nickname} removed.`);
      setRemoving(null);
      onChanged();
    } else {
      toast("error", r.message);
    }
  };

  if (loading && cards.length === 0) {
    return <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">{[0, 1].map((i) => <Skeleton key={i} className="h-[420px]" />)}</div>;
  }
  if (cards.length === 0) {
    return (
      <EmptyState icon={CreditCard} title="No cards yet"
        text="Add your first credit card to track limits, dues and utilisation in one place."
        action={<Button onClick={onAdd}><Plus className="w-4 h-4" /> Add credit card</Button>} />
    );
  }
  return (
    <>
      <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <AnimatePresence initial={false}>
          {cards.map((c) => <CreditCardItem key={c.card_id} card={c} onRemove={setRemoving} />)}
        </AnimatePresence>
      </div>
      <AnimatePresence>
        {removing && (
          <ConfirmDialog danger busy={busy} title="Remove this card?" confirmLabel="Remove card"
            message={`${removing.issuer_name} · ${removing.card_nickname} (•••• ${removing.last_four_digits}) will be removed and its stored figures deleted.${removing.card_source === "PROVIDER" ? " Data-sharing consent for this card will also be revoked." : ""} Your payment records are kept for your reference.`}
            onConfirm={confirmRemove} onClose={() => setRemoving(null)} />
        )}
      </AnimatePresence>
    </>
  );
}
