import { useEffect, useMemo, useRef, useState } from "react";
import { PencilLine, ShieldCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { cleanAmount, previewFigures, validateCardForm } from "../../utils/validation";
import { fmtINR } from "../../utils/format";
import { Banner, Button, Field, inputCls, useToast } from "../ui";

// Fallback only — the list comes from the card_networks table via /cards/networks.
const FALLBACK_NETWORKS = [["VISA", "Visa"], ["MASTERCARD", "Mastercard"], ["RUPAY", "RuPay"], ["AMEX", "American Express"], ["DINERS", "Diners Club"], ["OTHER", "Other"]];
const EMPTY = {
  issuer_name: "", card_nickname: "", card_network: "", last_four_digits: "", credit_limit: "",
  outstanding_balance: "", available_credit: "", minimum_amount_due: "", billing_day: "", due_date: "",
};

/** Manual entry: the ONLY card data collected is the last 4 digits. Never the
 *  full number, CVV, expiry, PIN, OTP or bank credentials. Also used to edit
 *  the figures of an existing user-entered card (pass `card`). */
export function ManualCardForm({ issuer, card, onSaved, onCancel }) {
  const { api } = useAuth();
  const toast = useToast();
  const editing = !!card;
  const [f, setF] = useState(() => editing ? {
    ...EMPTY, card_nickname: card.card_nickname,
    credit_limit: card.credit_limit ?? "", outstanding_balance: card.outstanding_balance ?? "",
    available_credit: card.available_credit_basis === "REPORTED" ? card.available_credit ?? "" : "",
    minimum_amount_due: card.minimum_amount_due ?? "", billing_day: card.billing_day ?? "", due_date: card.due_date ?? "",
  } : EMPTY);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [saving, setSaving] = useState(false);
  const submitted = useRef(false);
  const [networks, setNetworks] = useState(FALLBACK_NETWORKS);
  useEffect(() => {
    if (editing) return;
    api("/cards/networks").then((r) => r.ok && r.data.networks.length && setNetworks(r.data.networks.map((n) => [n.code, n.name])));
  }, [api, editing]);

  const isOther = !editing && issuer?.code === "OTHER";
  const set = (k) => (e) => {
    let v = e.target.value;
    if (k === "last_four_digits") v = v.replace(/\D/g, "").slice(0, 4);
    if (["credit_limit", "outstanding_balance", "available_credit", "minimum_amount_due"].includes(k)) v = v.replace(/[^\d.,]/g, "");
    if (k === "billing_day") v = v.replace(/\D/g, "").slice(0, 2);
    const next = { ...f, [k]: v };
    setF(next);
    if (touched[k] || submitted.current) setErrors(validateCardForm(next, { requireIssuerName: isOther }));
  };
  const blur = (k) => () => { setTouched((t) => ({ ...t, [k]: true })); setErrors(validateCardForm(f, { requireIssuerName: isOther })); };
  const err = (k) => (touched[k] || submitted.current ? errors[k] : "");
  const preview = useMemo(() => previewFigures(f), [f]);

  const submit = async (e) => {
    e.preventDefault();
    if (saving) return;                      // double-submit guard
    submitted.current = true;
    const v = validateCardForm(f, { requireIssuerName: isOther });
    setErrors(v);
    if (Object.keys(v).length) return;

    const amt = (k) => (cleanAmount(f[k]) === "" ? null : cleanAmount(f[k]));
    const body = {
      card_nickname: f.card_nickname.trim(),
      credit_limit: amt("credit_limit"), outstanding_balance: amt("outstanding_balance"),
      available_credit: amt("available_credit"), minimum_amount_due: amt("minimum_amount_due"),
      billing_day: f.billing_day === "" ? null : Number(f.billing_day), due_date: f.due_date || null,
    };
    if (!editing) {
      Object.assign(body, { issuer_id: issuer.issuer_id, last_four_digits: f.last_four_digits,
                            card_network: f.card_network || null });
      if (isOther) body.issuer_name = f.issuer_name.trim();
    }
    setSaving(true);
    const r = await api(editing ? `/cards/${card.card_id}` : "/cards", { method: editing ? "PATCH" : "POST", body });
    setSaving(false);
    if (r.ok) {
      toast("success", editing ? "Card updated." : "Card added — figures are user-entered and not bank verified.");
      onSaved(r.data.card);
    } else {
      if (Object.keys(r.errors).length) setErrors(r.errors);
      toast("error", r.message);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <Banner tone="warn" icon={PencilLine}>
        Values you enter are labelled <b>User-entered — Not Bank Verified</b>. Entering them does not verify that you own
        this card or confirm its limit or balance with your bank.
      </Banner>

      {isOther && (
        <Field label="Bank name" error={err("issuer_name")}>
          <input className={inputCls(err("issuer_name"))} value={f.issuer_name} onChange={set("issuer_name")} onBlur={blur("issuer_name")}
            placeholder="e.g. Saraswat Bank" maxLength={100} />
        </Field>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2 sm:col-span-1">
          <Field label="Card nickname" error={err("card_nickname")}>
            <input className={inputCls(err("card_nickname"))} value={f.card_nickname} onChange={set("card_nickname")}
              onBlur={blur("card_nickname")} placeholder="e.g. Travel card" maxLength={40} autoFocus />
          </Field>
        </div>
        {!editing && (
          <div className="col-span-2 sm:col-span-1">
            <Field label="Card type" optional>
              <select className={inputCls()} value={f.card_network} onChange={set("card_network")}>
                <option value="" className="bg-[#141C30]">Select</option>
                {networks.map(([code, name]) => <option key={code} value={code} className="bg-[#141C30]">{name}</option>)}
              </select>
            </Field>
          </div>
        )}
      </div>

      {!editing && (
        <Field label="Last 4 digits of card" hint="Only these 4 digits are stored" error={err("last_four_digits")}>
          <div className="relative">
            <span className="absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-gray-600 tracking-widest text-sm">•••• •••• ••••</span>
            <input className={`${inputCls(err("last_four_digits"))} pl-[8.5rem] font-mono tracking-[0.3em]`} inputMode="numeric"
              autoComplete="off" value={f.last_four_digits} onChange={set("last_four_digits")} onBlur={blur("last_four_digits")} placeholder="1234" />
          </div>
        </Field>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Total credit limit (₹)" error={err("credit_limit")}>
          <input className={inputCls(err("credit_limit"))} inputMode="decimal" value={f.credit_limit} onChange={set("credit_limit")}
            onBlur={blur("credit_limit")} placeholder="200000" />
        </Field>
        <Field label="Outstanding balance (₹)" optional error={err("outstanding_balance")}>
          <input className={inputCls(err("outstanding_balance"))} inputMode="decimal" value={f.outstanding_balance}
            onChange={set("outstanding_balance")} onBlur={blur("outstanding_balance")} placeholder="45000" />
        </Field>
        <Field label="Available credit (₹)" optional hint="if your bank shows it" error={err("available_credit")}>
          <input className={inputCls(err("available_credit"))} inputMode="decimal" value={f.available_credit}
            onChange={set("available_credit")} onBlur={blur("available_credit")} placeholder="—" />
        </Field>
        <Field label="Minimum amount due (₹)" optional error={err("minimum_amount_due")}>
          <input className={inputCls(err("minimum_amount_due"))} inputMode="decimal" value={f.minimum_amount_due}
            onChange={set("minimum_amount_due")} onBlur={blur("minimum_amount_due")} placeholder="—" />
        </Field>
        <Field label="Billing cycle date" optional hint="day of month" error={err("billing_day")}>
          <input className={inputCls(err("billing_day"))} inputMode="numeric" value={f.billing_day} onChange={set("billing_day")}
            onBlur={blur("billing_day")} placeholder="e.g. 12" />
        </Field>
        <Field label="Payment due date" optional error={err("due_date")}>
          <input type="date" className={`${inputCls(err("due_date"))} [color-scheme:dark]`} value={f.due_date}
            onChange={set("due_date")} onBlur={blur("due_date")} />
        </Field>
      </div>

      <div className="rounded-xl border border-white/10 bg-[#141C30]/60 p-3 grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="text-gray-500">Utilisation</div>
          <div className="text-white font-semibold text-sm">{preview.utilization === null ? "—" : `${preview.utilization.toFixed(2)}%`}</div>
        </div>
        <div>
          <div className="text-gray-500">Available credit {preview.availableBasis === "ESTIMATED" && "(estimate)"}</div>
          <div className="text-white font-semibold text-sm">{preview.available === null ? "—" : fmtINR(preview.available)}</div>
        </div>
        {preview.availableBasis === "ESTIMATED" && (
          <p className="col-span-2 text-gray-500">Estimate = limit − outstanding. Your bank's figure may differ due to pending transactions, holds, refunds or fees.</p>
        )}
      </div>

      <div className="flex items-center gap-2 text-[11px] text-gray-500">
        <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" /> We never ask for your full card number, CVV, expiry, PIN, OTP or bank password.
      </div>

      <div className="flex gap-2 pt-1">
        <Button type="button" variant="ghost" className="flex-1" onClick={onCancel} disabled={saving}>{editing ? "Cancel" : "Back"}</Button>
        <Button type="submit" className="flex-1" loading={saving}>{editing ? "Save changes" : "Add card"}</Button>
      </div>
    </form>
  );
}
