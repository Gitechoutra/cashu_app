import { useCallback, useEffect, useState } from "react";
import { AnimatePresence } from "motion/react";
import { Fingerprint, KeyRound, LogOut, ShieldCheck, Trash2, UserRound } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Button, ConfirmDialog, Field, ModalShell, Pill, Skeleton, inputCls, useToast } from "../../components/ui";
import { createCredential, isBiometricAvailable } from "../../utils/webauthn";
import { validateName, validatePin } from "../../utils/validation";
import { fmtDate, timeAgo } from "../../utils/format";
import { pinLengthFor } from "../../utils/roles";
import { BankAccountsSection, DevicesAndActivity, KycStatus, ProfileDetails, SecurityPreferences } from "./SettingsSections";

export function UserSettings() {
  const { api, user, setUser, logout } = useAuth();
  const toast = useToast();
  const [sec, setSec] = useState(null);
  const [consents, setConsents] = useState([]);
  const [bioAvail, setBioAvail] = useState(false);
  const [name, setName] = useState(user?.full_name || "");
  const [nameErr, setNameErr] = useState("");
  const [busy, setBusy] = useState("");
  const [pinOpen, setPinOpen] = useState(false);
  const [revoke, setRevoke] = useState(null);

  const load = useCallback(async () => {
    const [s, c] = await Promise.all([api("/security/settings"),
      user?.role === "USER" ? api("/cards/consents") : Promise.resolve({ ok: false })]);
    if (s.ok) setSec(s.data);
    if (c.ok) setConsents(c.data.consents);
  }, [api]);
  useEffect(() => { load(); isBiometricAvailable().then(setBioAvail); }, [load]);

  const saveName = async () => {
    const e = validateName(name);
    setNameErr(e);
    if (e) return;
    setBusy("name");
    const r = await api("/authentication/me", { method: "PATCH", body: { full_name: name.trim() } });
    setBusy("");
    if (r.ok) { setUser(r.data); toast("success", "Name updated."); } else setNameErr(r.message);
  };

  const enableBio = async () => {
    setBusy("bio");
    try {
      const o = await api("/security/webauthn/register/options", { method: "POST" });
      if (!o.ok) throw new Error(o.message);
      const credential = await createCredential(o.data.options);
      const r = await api("/security/webauthn/register/verify", { method: "POST", body: { credential, label: navigator.platform || "This device" } });
      if (!r.ok) throw new Error(r.message);
      toast("success", "Biometric unlock enabled.");
      setUser({ ...user, biometric_enabled: true });
      load();
    } catch (e) {
      toast("error", e?.name === "NotAllowedError" ? "Biometric setup was cancelled." : e?.message || "Could not enable biometrics.");
    } finally { setBusy(""); }
  };

  const removeBio = async (id) => {
    const r = await api(`/security/webauthn/${id}`, { method: "DELETE" });
    if (r.ok) { toast("success", "Biometric device removed."); load(); } else toast("error", r.message);
  };

  const doRevoke = async () => {
    setBusy("revoke");
    const r = await api(`/cards/consents/${revoke.consent_id}/revoke`, { method: "POST" });
    setBusy("");
    if (r.ok) { toast("success", "Consent revoked."); setRevoke(null); load(); } else toast("error", r.message);
  };

  return (
    <div className="p-4 lg:p-8 max-w-3xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-white">Settings</h1>

      <Section icon={UserRound} title="Profile">
        <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
          <div className="flex-1"><Field label="Full name" error={nameErr}><input className={inputCls(nameErr)} value={name} maxLength={100} onChange={(e) => { setName(e.target.value); setNameErr(""); }} /></Field></div>
          <Button onClick={saveName} loading={busy === "name"} disabled={name.trim() === user?.full_name}>Save</Button>
        </div>
        <p className="text-xs text-gray-500 mt-3">Mobile: {user?.mobile_number} (verified by OTP){user?.seed_managed ? " · name, mobile and PIN are managed by your administrator" : ""}</p>
      </Section>

      <ProfileDetails />
      {user?.role === "USER" && <KycStatus />}

      <Section icon={ShieldCheck} title="Security">
        {!sec ? <Skeleton className="h-24" /> : (
          <div className="space-y-4">
            <Row icon={KeyRound} title="App PIN" text={`Set ${fmtDate(sec.pin_set_at)} · app locks after ${sec.idle_lock_minutes} min of inactivity`}
              action={<Button variant="ghost" size="sm" onClick={() => setPinOpen(true)}>Change PIN</Button>} />
            <div>
              <Row icon={Fingerprint} title="Fingerprint / Face unlock"
                text={sec.biometrics.length ? `${sec.biometrics.length} device(s) enrolled` : bioAvail ? "Not enabled on this device" : "Not supported by this device or browser"}
                action={bioAvail && <Button variant="ghost" size="sm" onClick={enableBio} loading={busy === "bio"}>Enable here</Button>} />
              {sec.biometrics.map((b) => (
                <div key={b.id} className="ml-11 mt-2 flex items-center justify-between text-xs text-gray-400">
                  <span>{b.label} · added {fmtDate(b.created_on)}{b.last_used_on ? ` · used ${timeAgo(b.last_used_on)}` : ""}</span>
                  <button onClick={() => removeBio(b.id)} className="p-1.5 rounded-lg hover:text-red-300 hover:bg-red-500/10" aria-label="Remove"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
          </div>
        )}
      </Section>

      <SecurityPreferences isCustomer={user?.role === "USER"} />
      <DevicesAndActivity />
      {user?.role === "USER" && <BankAccountsSection />}

      {user?.role === "USER" && <Section icon={ShieldCheck} title="Data & consents">
        {consents.length === 0 ? (
          <p className="text-sm text-gray-500">No bank data-sharing consents. Manually added cards share nothing with third parties.</p>
        ) : consents.map((c) => (
          <div key={c.consent_id} className="flex items-start justify-between gap-3 py-2">
            <div className="min-w-0">
              <div className="text-sm text-white">{c.provider_name} <Pill className={c.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-white/5 text-gray-400 border-white/10"}>{c.status}</Pill></div>
              <div className="text-xs text-gray-500">{c.purpose}</div>
              <div className="text-[11px] text-gray-600">Granted {fmtDate(c.created_at)}{c.consent_expires_at ? ` · expires ${fmtDate(c.consent_expires_at)}` : ""}{c.cards.length ? ` · ${c.cards.join(", ")}` : ""}</div>
            </div>
            {c.status === "ACTIVE" && <Button variant="ghost" size="sm" onClick={() => setRevoke(c)}>Revoke</Button>}
          </div>
        ))}
        <p className="text-[11px] text-gray-600 mt-3">Removing a card deletes its stored figures and history. Payment receipts are retained for reconciliation.</p>
      </Section>}

      <Button variant="ghost" className="w-full" onClick={logout}><LogOut className="w-4 h-4" /> Sign out of this device</Button>

      <AnimatePresence>
        {pinOpen && <ChangePin onClose={() => setPinOpen(false)} onDone={() => { setPinOpen(false); load(); }} />}
        {revoke && (
          <ConfirmDialog danger busy={busy === "revoke"} title="Revoke consent?" confirmLabel="Revoke"
            message={`${revoke.provider_name} will stop sharing data. Linked cards keep their last verified figures but can no longer refresh.`}
            onConfirm={doRevoke} onClose={() => setRevoke(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}

function ChangePin({ onClose, onDone }) {
  const { api, user } = useAuth();
  const len = pinLengthFor(user?.role);
  const toast = useToast();
  const [f, setF] = useState({ current: "", next: "", confirm: "" });
  const [err, setErr] = useState({});
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value.replace(/\D/g, "").slice(0, len) });
  const submit = async (e) => {
    e.preventDefault();
    const er = {};
    if (f.current.length !== len) er.current = `Enter your current ${len}-digit PIN.`;
    const p = validatePin(f.next); if (p) er.next = p;
    if (!er.next && f.next.length !== len) er.next = `Use ${len} digits.`;
    if (f.confirm !== f.next) er.confirm = "PINs don't match.";
    setErr(er);
    if (Object.keys(er).length || busy) return;
    setBusy(true);
    const r = await api("/security/pin", { method: "POST", body: { current_pin: f.current, new_pin: f.next } });
    setBusy(false);
    if (r.ok) { toast("success", "PIN changed."); onDone(); }
    else setErr(r.errors && Object.keys(r.errors).length ? { current: r.errors.current_pin, next: r.errors.new_pin } : { current: r.message });
  };
  const pinInput = (k) => <input type="password" inputMode="numeric" autoComplete="off" className={`${inputCls(err[k])} tracking-[0.5em] font-mono`} value={f[k]} onChange={set(k)} />;
  return (
    <ModalShell title="Change app PIN" onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        <Field label="Current PIN" error={err.current}>{pinInput("current")}</Field>
        <Field label="New PIN" error={err.next}>{pinInput("next")}</Field>
        <Field label="Confirm new PIN" error={err.confirm}>{pinInput("confirm")}</Field>
        <Banner>Never share your PIN. CardVault staff will never ask for it.</Banner>
        <Button type="submit" className="w-full" loading={busy}>Update PIN</Button>
      </form>
    </ModalShell>
  );
}

function Section({ icon: Icon, title, children }) {
  return (
    <section className="bg-[#0C1220] border border-white/5 rounded-2xl p-5">
      <h2 className="text-sm font-semibold text-white flex items-center gap-2 mb-4"><Icon className="w-4 h-4 text-cyan-300" /> {title}</h2>
      {children}
    </section>
  );
}

function Row({ icon: Icon, title, text, action }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center shrink-0"><Icon className="w-4 h-4 text-gray-300" /></div>
      <div className="flex-1 min-w-0"><div className="text-sm text-white">{title}</div><div className="text-xs text-gray-500">{text}</div></div>
      {action}
    </div>
  );
}
