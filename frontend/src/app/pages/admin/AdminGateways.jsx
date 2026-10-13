import { useCallback, useEffect, useState } from "react";
import { AnimatePresence } from "motion/react";
import { CheckCircle2, KeyRound, Pencil, Plus, ShieldCheck, Trash2, Zap } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Button, ConfirmDialog, Field, ModalShell, Pill, Skeleton, inputCls, useToast } from "../../components/ui";
import { fmtDateTime } from "../../utils/format";

/** Payment gateway configuration. Secrets are write-only: the API never returns them. */
export function AdminGateways() {
  const { api } = useAuth();
  const toast = useToast();
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);     // gateway or {} for new
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    const r = await api("/admin/gateways");
    if (r.ok) setData(r.data); else toast("error", r.message);
  }, [api, toast]);
  useEffect(() => { load(); }, [load]);

  const patch = async (g, body, msg) => {
    setBusy(`p${g.gateway_id}`);
    const r = await api(`/admin/gateways/${g.gateway_id}`, { method: "PATCH", body });
    setBusy("");
    if (r.ok) { toast("success", msg); load(); } else toast("error", r.message);
  };
  const test = async (g) => {
    setBusy(`t${g.gateway_id}`);
    const r = await api(`/admin/gateways/${g.gateway_id}/test`, { method: "POST" });
    setBusy("");
    toast(r.ok ? "success" : "error", r.ok ? r.data.message : r.message);
  };
  const remove = async () => {
    setBusy("d");
    const r = await api(`/admin/gateways/${deleting.gateway_id}`, { method: "DELETE" });
    setBusy("");
    if (r.ok) { toast("success", "Gateway deleted."); setDeleting(null); load(); } else toast("error", r.message);
  };

  return (
    <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-white flex items-center gap-2"><KeyRound className="w-5 h-5 text-amber-300" /> Payment gateways</h1>
        <Button onClick={() => setEditing({})}><Plus className="w-4 h-4" /> <span className="hidden sm:inline">Add gateway</span></Button>
      </div>
      {data && (
        <Banner tone={data.status.configured ? "success" : "warn"} icon={ShieldCheck}>
          Payments currently use <b>{data.active_source === "ADMIN" ? "the active gateway below" : "the keys in the server .env file"}</b>
          {data.status.mode ? ` · ${data.status.mode} mode` : ""}. {data.status.message}
        </Banner>
      )}
      {!data ? <Skeleton className="h-40" /> : data.gateways.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-gray-500">
          No gateways configured here yet — payments fall back to RAZORPAY_* in the server .env.
        </div>
      ) : (
        <div className="space-y-3">
          {data.gateways.map((g) => (
            <div key={g.gateway_id} className={`bg-[#0C1220] border rounded-2xl p-5 ${g.is_active ? "border-emerald-500/30" : "border-white/5"}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-white font-semibold">{g.display_name}</span>
                    {g.is_active && <Pill className="bg-emerald-500/10 text-emerald-300 border-emerald-500/25"><CheckCircle2 className="w-3 h-3" /> Active</Pill>}
                    <Pill className={g.mode === "live" ? "bg-red-500/10 text-red-300 border-red-500/25" : "bg-amber-500/10 text-amber-200 border-amber-500/25"}>{g.mode.toUpperCase()}</Pill>
                  </div>
                  <dl className="mt-2 grid sm:grid-cols-3 gap-x-6 gap-y-1 text-xs">
                    <div><dt className="text-gray-500">Key id</dt><dd className="text-gray-200 font-mono">{g.key_id}</dd></div>
                    <div><dt className="text-gray-500">Key secret</dt><dd className="text-gray-200 font-mono">{g.key_secret || "—"}</dd></div>
                    <div><dt className="text-gray-500">Webhook secret</dt><dd className="text-gray-200 font-mono">{g.webhook_secret || "not set"}</dd></div>
                  </dl>
                  <div className="text-[11px] text-gray-600 mt-2">Updated {fmtDateTime(g.updated_at)}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="ghost" loading={busy === `t${g.gateway_id}`} onClick={() => test(g)}><Zap className="w-3.5 h-3.5" /> Test</Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(g)}><Pencil className="w-3.5 h-3.5" /> Edit</Button>
                  {g.is_active
                    ? <Button size="sm" variant="ghost" loading={busy === `p${g.gateway_id}`} onClick={() => patch(g, { is_active: false }, "Gateway deactivated — falling back to .env.")}>Deactivate</Button>
                    : <Button size="sm" loading={busy === `p${g.gateway_id}`} onClick={() => patch(g, { is_active: true }, "Gateway activated.")}>Activate</Button>}
                  {!g.is_active && <button onClick={() => setDeleting(g)} aria-label="Delete" className="p-2 rounded-lg text-gray-500 hover:text-red-300 hover:bg-red-500/10"><Trash2 className="w-4 h-4" /></button>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="text-[11px] text-gray-600">Secrets are encrypted at rest and can only be replaced, never viewed. Live keys stay disabled for bill payments until a BBPS settlement partner is configured.</p>

      <AnimatePresence>
        {editing && <GatewayForm gw={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
        {deleting && <ConfirmDialog danger busy={busy === "d"} title="Delete gateway?" confirmLabel="Delete"
          message={`${deleting.display_name} and its encrypted secrets will be permanently deleted.`} onConfirm={remove} onClose={() => setDeleting(null)} />}
      </AnimatePresence>
    </div>
  );
}

function GatewayForm({ gw, onClose, onSaved }) {
  const { api } = useAuth();
  const toast = useToast();
  const isNew = !gw.gateway_id;
  const [f, setF] = useState({ display_name: gw.display_name || "Razorpay", key_id: gw.key_id || "", key_secret: "", webhook_secret: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    const body = { display_name: f.display_name, key_id: f.key_id.trim() };
    if (f.key_secret) body.key_secret = f.key_secret;
    if (f.webhook_secret) body.webhook_secret = f.webhook_secret;
    setBusy(true);
    const r = await api(isNew ? "/admin/gateways" : `/admin/gateways/${gw.gateway_id}`, { method: isNew ? "POST" : "PATCH", body });
    setBusy(false);
    if (r.ok) { toast("success", isNew ? "Gateway added (inactive). Test it, then activate." : "Gateway updated."); onSaved(); }
    else { setErrors(r.errors || {}); toast("error", r.message); }
  };

  return (
    <ModalShell title={isNew ? "Add Razorpay gateway" : `Edit ${gw.display_name}`} subtitle="Razorpay Dashboard → Account & Settings → API Keys" onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="space-y-3" noValidate autoComplete="off">
        <Field label="Display name" error={errors.display_name}><input className={inputCls(errors.display_name)} value={f.display_name} onChange={set("display_name")} maxLength={60} /></Field>
        <Field label="Key id" error={errors.key_id}><input className={`${inputCls(errors.key_id)} font-mono`} value={f.key_id} onChange={set("key_id")} placeholder="rzp_test_…" /></Field>
        <Field label="Key secret" error={errors.key_secret} hint={isNew ? "required" : "leave blank to keep current"}>
          <input type="password" autoComplete="new-password" className={`${inputCls(errors.key_secret)} font-mono`} value={f.key_secret} onChange={set("key_secret")} />
        </Field>
        <Field label="Webhook secret" optional error={errors.webhook_secret} hint={isNew ? "" : "leave blank to keep current"}>
          <input type="password" autoComplete="new-password" className={`${inputCls(errors.webhook_secret)} font-mono`} value={f.webhook_secret} onChange={set("webhook_secret")} />
        </Field>
        <Banner>Webhook URL to configure in Razorpay: <span className="font-mono break-all">https://&lt;your-domain&gt;/v1/bills/webhook</span> (events: payment.captured, payment.authorized, payment.failed).</Banner>
        <Button type="submit" className="w-full" loading={busy}>{isNew ? "Save gateway" : "Save changes"}</Button>
      </form>
    </ModalShell>
  );
}
