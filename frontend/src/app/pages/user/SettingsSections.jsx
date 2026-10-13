import { useCallback, useEffect, useState } from "react";
import { AnimatePresence } from "motion/react";
import {
  Activity, BadgeCheck, Bell, Building2, Landmark, Mail, MonitorSmartphone, Plus, Star, Timer, Trash2,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Button, ConfirmDialog, Field, ModalShell, Pill, Skeleton, inputCls, useToast } from "../../components/ui";
import { fmtDateTime, timeAgo } from "../../utils/format";

export function Section({ icon: Icon, title, children, action }) {
  return (
    <section className="bg-[#0C1220] border border-white/5 rounded-2xl p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2"><Icon className="w-4 h-4 text-cyan-300" /> {title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/* ── Contact & language ──────────────────────────────────────────────────── */
export function ProfileDetails() {
  const { api } = useAuth();
  const toast = useToast();
  const [p, setP] = useState(null);
  const [f, setF] = useState({ email: "", city: "", state: "", preferred_language: "en" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api("/account/profile").then((r) => {
      if (!r.ok) return;
      setP(r.data);
      setF({ email: r.data.email || "", city: r.data.city || "", state: r.data.state || "", preferred_language: r.data.preferred_language });
    });
  }, [api]);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await api("/account/profile", { method: "PATCH", body: f });
    setBusy(false);
    if (r.ok) { setP(r.data); setErrors({}); toast("success", "Profile saved."); } else { setErrors(r.errors || {}); toast("error", r.message); }
  };

  if (!p) return <Skeleton className="h-40" />;
  return (
    <Section icon={Mail} title="Contact & language">
      <form onSubmit={save} className="grid sm:grid-cols-2 gap-3" noValidate>
        <div className="sm:col-span-2">
          <Field label="Email" optional error={errors.email} hint={p.email ? (p.email_verified ? "verified" : "not verified") : ""}>
            <input type="email" className={inputCls(errors.email)} value={f.email} maxLength={254} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="you@example.com" />
          </Field>
        </div>
        <Field label="City" optional error={errors.city}><input className={inputCls(errors.city)} value={f.city} maxLength={60} onChange={(e) => setF({ ...f, city: e.target.value })} /></Field>
        <Field label="State" optional error={errors.state}><input className={inputCls(errors.state)} value={f.state} maxLength={60} onChange={(e) => setF({ ...f, state: e.target.value })} /></Field>
        <Field label="Preferred language">
          <select className={inputCls()} value={f.preferred_language} onChange={(e) => setF({ ...f, preferred_language: e.target.value })}>
            {Object.entries(p.languages).map(([k, v]) => <option key={k} value={k} className="bg-[#141C30]">{v}</option>)}
          </select>
        </Field>
        <div className="flex items-end"><Button type="submit" className="w-full" loading={busy}>Save</Button></div>
      </form>
    </Section>
  );
}

/* ── Alerts & auto-lock ──────────────────────────────────────────────────── */
export function SecurityPreferences({ isCustomer }) {
  const { api } = useAuth();
  const toast = useToast();
  const [p, setP] = useState(null);
  useEffect(() => { api("/account/preferences").then((r) => r.ok && setP(r.data)); }, [api]);

  const update = async (patch) => {
    const r = await api("/account/preferences", { method: "PATCH", body: patch });
    if (r.ok) { setP(r.data); toast("success", "Preferences saved."); } else toast("error", r.message);
  };

  if (!p) return <Skeleton className="h-32" />;
  return (
    <Section icon={Bell} title="Alerts & auto-lock">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Timer className="w-4 h-4 text-gray-400 shrink-0" />
          <div className="flex-1 min-w-0"><div className="text-sm text-white">Auto-lock after inactivity</div><div className="text-xs text-gray-500">Can only be shorter than the {p.server_idle_lock_minutes}-minute app limit.</div></div>
          <select className="text-sm rounded-lg bg-[#141C30] border border-white/10 px-2 py-2 text-gray-200" value={p.idle_lock_minutes ?? ""}
            onChange={(e) => update({ idle_lock_minutes: e.target.value === "" ? null : Number(e.target.value) })}>
            <option value="">Default ({p.server_idle_lock_minutes} min)</option>
            {p.idle_choices.filter((m) => m < p.server_idle_lock_minutes).map((m) => <option key={m} value={m}>{m} min</option>)}
          </select>
        </div>
        <Toggle label="New-device sign-in alerts" text="Notify me when my account is used on a new device." checked={p.login_alerts} onChange={(v) => update({ login_alerts: v })} />
        {isCustomer && <Toggle label="Payment alerts" text="Notify me when a bill payment succeeds or fails." checked={p.payment_alerts} onChange={(v) => update({ payment_alerts: v })} />}
      </div>
    </Section>
  );
}

function Toggle({ label, text, checked, onChange }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <div className="flex-1 min-w-0"><div className="text-sm text-white">{label}</div><div className="text-xs text-gray-500">{text}</div></div>
      <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={`w-11 h-6 rounded-full transition-colors relative shrink-0 ${checked ? "bg-cyan-500" : "bg-white/15"}`}>
        <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ${checked ? "left-[22px]" : "left-0.5"}`} />
      </button>
    </label>
  );
}

/* ── Devices & recent activity ───────────────────────────────────────────── */
const EVENT_LABEL = { OTP_LOGIN: "Sign-in with OTP", PIN_UNLOCK: "Unlock with PIN", BIOMETRIC_UNLOCK: "Unlock with biometrics", LOGOUT: "Sign-out" };

export function DevicesAndActivity() {
  const { api } = useAuth();
  const toast = useToast();
  const [devices, setDevices] = useState(null);
  const [history, setHistory] = useState([]);
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const [d, h] = await Promise.all([api("/account/devices"), api("/account/login-history?per_page=10")]);
    if (d.ok) setDevices(d.data.devices);
    if (h.ok) setHistory(h.data.items);
  }, [api]);
  useEffect(() => { load(); }, [load]);

  const remove = async () => {
    setBusy(true);
    const r = await api(`/account/devices/${removing.device_id}`, { method: "DELETE" });
    setBusy(false);
    if (r.ok) { toast("success", "Device signed out."); setRemoving(null); load(); } else toast("error", r.message);
  };

  return (
    <>
      <Section icon={MonitorSmartphone} title="Devices">
        {!devices ? <Skeleton className="h-20" /> : devices.length === 0 ? <p className="text-sm text-gray-500">No devices recorded yet.</p> : (
          <ul className="space-y-2">
            {devices.map((d) => (
              <li key={d.device_id} className="flex items-center gap-3 text-sm">
                <MonitorSmartphone className="w-4 h-4 text-gray-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-white truncate">{d.name || "Unknown device"} {d.current && <Pill className="bg-cyan-500/10 text-cyan-300 border-cyan-500/20 ml-1">This device</Pill>}</div>
                  <div className="text-[11px] text-gray-500">Last active {timeAgo(d.last_seen_at)} · first seen {fmtDateTime(d.first_seen_at)}</div>
                </div>
                {!d.current && <button onClick={() => setRemoving(d)} className="text-xs text-red-300/80 hover:text-red-300">Sign out</button>}
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section icon={Activity} title="Recent activity">
        {history.length === 0 ? <p className="text-sm text-gray-500">No activity yet.</p> : (
          <ul className="divide-y divide-white/5 -my-2">
            {history.map((h, i) => (
              <li key={i} className="py-2 flex items-center justify-between gap-3 text-xs">
                <div className="min-w-0">
                  <div className="text-gray-200">{EVENT_LABEL[h.event] || h.event}</div>
                  <div className="text-gray-500 truncate">{h.device || "Unknown device"}{h.ip_address ? ` · ${h.ip_address}` : ""}</div>
                </div>
                <div className="text-right shrink-0">
                  <Pill className={h.status === "SUCCESS" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-red-500/10 text-red-300 border-red-500/20"}>{h.status === "SUCCESS" ? "OK" : h.status}</Pill>
                  <div className="text-gray-600 mt-1">{timeAgo(h.created_at)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="text-[11px] text-gray-600 mt-3">Don't recognise something? Sign out that device and change your PIN.</p>
      </Section>
      <AnimatePresence>
        {removing && <ConfirmDialog danger busy={busy} title="Sign out this device?" confirmLabel="Sign out"
          message={`${removing.name || "This device"} will be signed out and will need OTP to sign in again.`} onConfirm={remove} onClose={() => setRemoving(null)} />}
      </AnimatePresence>
    </>
  );
}

/* ── KYC (customers) ─────────────────────────────────────────────────────── */
export function KycStatus() {
  const { api } = useAuth();
  const [k, setK] = useState(null);
  useEffect(() => { api("/account/kyc").then((r) => r.ok && setK(r.data)); }, [api]);
  if (!k) return null;
  const tone = { VERIFIED: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20", PENDING: "bg-amber-500/10 text-amber-300 border-amber-500/20",
    REJECTED: "bg-red-500/10 text-red-300 border-red-500/20", NOT_STARTED: "bg-white/5 text-gray-300 border-white/10" }[k.status];
  return (
    <Section icon={BadgeCheck} title="KYC" action={<Pill className={tone}>{k.status.replace("_", " ")}</Pill>}>
      {k.status === "VERIFIED" ? <p className="text-sm text-gray-400">Verified {fmtDateTime(k.verified_at)} via {k.method}.</p>
        : <Banner>{k.message}</Banner>}
    </Section>
  );
}

/* ── Bank accounts (customers) ───────────────────────────────────────────── */
export function BankAccountsSection() {
  const { api } = useAuth();
  const toast = useToast();
  const [data, setData] = useState(null);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { const r = await api("/account/bank-accounts"); if (r.ok) setData(r.data); }, [api]);
  useEffect(() => { load(); }, [load]);

  const primary = async (b) => {
    const r = await api(`/account/bank-accounts/${b.bank_account_id}/primary`, { method: "POST" });
    if (r.ok) load(); else toast("error", r.message);
  };
  const remove = async () => {
    setBusy(true);
    const r = await api(`/account/bank-accounts/${removing.bank_account_id}`, { method: "DELETE" });
    setBusy(false);
    if (r.ok) { toast("success", "Bank account removed."); setRemoving(null); load(); } else toast("error", r.message);
  };

  return (
    <Section icon={Landmark} title="Bank accounts" action={<Button size="sm" variant="ghost" onClick={() => setAdding(true)}><Plus className="w-3.5 h-3.5" /> Add</Button>}>
      {!data ? <Skeleton className="h-16" /> : (
        <>
          {data.bank_accounts.length === 0 ? <p className="text-sm text-gray-500">No bank accounts saved.</p> : (
            <ul className="space-y-2">
              {data.bank_accounts.map((b) => (
                <li key={b.bank_account_id} className="flex items-center gap-3 text-sm">
                  <Building2 className="w-4 h-4 text-gray-500 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-white truncate">{b.bank_name} · <span className="font-mono">{b.masked_account}</span></div>
                    <div className="text-[11px] text-gray-500">{b.account_holder_name} · {b.ifsc} · {b.account_type.toLowerCase()}
                      {b.verification_status === "UNVERIFIED" && <span className="text-amber-300/80"> · not verified</span>}</div>
                  </div>
                  <button onClick={() => primary(b)} disabled={b.is_primary} aria-label="Set primary" title={b.is_primary ? "Primary" : "Make primary"}
                    className={`p-1.5 rounded-lg ${b.is_primary ? "text-amber-300" : "text-gray-600 hover:text-gray-300"}`}><Star className={`w-4 h-4 ${b.is_primary ? "fill-current" : ""}`} /></button>
                  <button onClick={() => setRemoving(b)} aria-label="Remove" className="p-1.5 rounded-lg text-gray-500 hover:text-red-300 hover:bg-red-500/10"><Trash2 className="w-4 h-4" /></button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-[11px] text-gray-600 mt-3">{data.message} Account numbers are encrypted; only the last 4 digits are shown.</p>
        </>
      )}
      <AnimatePresence>
        {adding && <AddBankAccount onClose={() => setAdding(false)} onDone={() => { setAdding(false); load(); }} />}
        {removing && <ConfirmDialog danger busy={busy} title="Remove bank account?" confirmLabel="Remove"
          message={`${removing.bank_name} ${removing.masked_account} will be deleted.`} onConfirm={remove} onClose={() => setRemoving(null)} />}
      </AnimatePresence>
    </Section>
  );
}

function AddBankAccount({ onClose, onDone }) {
  const { api } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ account_holder_name: "", bank_name: "", ifsc: "", account_number: "", confirm_account_number: "", account_type: "SAVINGS" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k, fn = (v) => v) => (e) => setF({ ...f, [k]: fn(e.target.value) });
  const submit = async (e) => {
    e.preventDefault();
    const er = {};
    if (!/^[A-Z]{4}0[A-Z0-9]{6}$/.test(f.ifsc)) er.ifsc = "Enter a valid 11-character IFSC.";
    if (!/^\d{9,18}$/.test(f.account_number)) er.account_number = "Account number must be 9 to 18 digits.";
    else if (f.account_number !== f.confirm_account_number) er.confirm_account_number = "Account numbers do not match.";
    setErrors(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    const r = await api("/account/bank-accounts", { method: "POST", body: f });
    setBusy(false);
    if (r.ok) { toast("success", "Bank account saved."); onDone(); } else { setErrors(r.errors || {}); toast("error", r.message); }
  };
  return (
    <ModalShell title="Add bank account" subtitle="Saved as not verified until account verification is set up." onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="space-y-3" noValidate autoComplete="off">
        <Field label="Account holder name" error={errors.account_holder_name}><input className={inputCls(errors.account_holder_name)} value={f.account_holder_name} onChange={set("account_holder_name")} maxLength={100} /></Field>
        <Field label="Bank name" error={errors.bank_name}><input className={inputCls(errors.bank_name)} value={f.bank_name} onChange={set("bank_name")} maxLength={100} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="IFSC" error={errors.ifsc}><input className={`${inputCls(errors.ifsc)} font-mono uppercase`} value={f.ifsc} onChange={set("ifsc", (v) => v.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 11))} placeholder="HDFC0001234" /></Field>
          <Field label="Type">
            <select className={inputCls()} value={f.account_type} onChange={set("account_type")}><option value="SAVINGS">Savings</option><option value="CURRENT">Current</option></select>
          </Field>
        </div>
        <Field label="Account number" error={errors.account_number}><input type="password" inputMode="numeric" autoComplete="off" className={`${inputCls(errors.account_number)} font-mono`} value={f.account_number} onChange={set("account_number", (v) => v.replace(/\D/g, "").slice(0, 18))} /></Field>
        <Field label="Confirm account number" error={errors.confirm_account_number}><input inputMode="numeric" autoComplete="off" className={`${inputCls(errors.confirm_account_number)} font-mono`} value={f.confirm_account_number} onChange={set("confirm_account_number", (v) => v.replace(/\D/g, "").slice(0, 18))} /></Field>
        <Button type="submit" className="w-full" loading={busy}>Save bank account</Button>
      </form>
    </ModalShell>
  );
}
