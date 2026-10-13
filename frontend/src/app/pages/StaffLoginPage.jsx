import { useState } from "react";
import { Link, Navigate } from "react-router";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Headset, KeyRound, Mail, ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Banner, Button, Field, inputCls } from "../components/ui";
import { PinPad } from "../components/PinPad";
import { validatePin } from "../utils/validation";
import { homeFor } from "../utils/roles";
import { Logo } from "./OnboardingPage";

const ROLE_UI = {
  ADMIN: { title: "Admin login", icon: ShieldCheck, accent: "from-amber-400 to-orange-600", ring: "focus:border-amber-500/50", text: "text-amber-300" },
  SUPPORT: { title: "Customer Support login", icon: Headset, accent: "from-violet-400 to-fuchsia-600", ring: "focus:border-violet-500/50", text: "text-violet-300" },
};

/** Staff sign-in: email + 6-digit PIN, no OTP. A temporary PIN must be replaced before continuing. */
export function StaffLoginPage({ role }) {
  const { status, user, staffLogin, api, finishOnboarding, logout } = useAuth();
  const ui = ROLE_UI[role];
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [tempPin, setTempPin] = useState("");

  if (status === "ready" && user) return <Navigate to={homeFor(user.role)} replace />;
  const mustReset = status === "onboarding" && user?.pin_reset_required;

  const submit = async (e) => {
    e?.preventDefault();
    if (busy) return;
    const em = email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(em)) { setErr("Enter a valid email address."); return; }
    if (!/^\d{6}$/.test(pin)) { setErr("Enter your 6-digit PIN."); return; }
    setBusy(true); setErr("");
    const r = await staffLogin(em, pin, role);
    setBusy(false);
    if (r.ok) { if (r.data.pin_reset_required) setTempPin(pin); setPin(""); }
    else { setErr(r.message); setPin(""); }
  };

  return (
    <div className="min-h-screen bg-[#070B14] bg-grid flex flex-col">
      <div className="absolute inset-0 bg-[radial-gradient(60%_40%_at_50%_0%,rgba(251,191,36,0.08),transparent)] pointer-events-none" />
      <header className="relative px-6 pt-8 max-w-md w-full mx-auto flex items-center justify-between">
        <Logo />
        <Link to="/" className="text-xs text-gray-500 hover:text-white inline-flex items-center gap-1"><ArrowLeft className="w-3.5 h-3.5" /> Home</Link>
      </header>
      <main className="relative flex-1 flex items-start sm:items-center justify-center px-5 py-10">
        <div className="w-full max-w-md bg-[#0C1220]/90 border border-white/8 rounded-3xl p-6 sm:p-8 shadow-2xl">
          <AnimatePresence mode="wait">
            {mustReset ? (
              <motion.div key="reset" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <ResetPin tempPin={tempPin} onDone={() => finishOnboarding({ pin_reset_required: false, has_pin: true })} onCancel={logout} api={api} />
              </motion.div>
            ) : (
              <motion.form key="login" onSubmit={submit} noValidate initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${ui.accent} flex items-center justify-center shadow-lg mb-4`}>
                  <ui.icon className="w-6 h-6 text-white" />
                </div>
                <h1 className="text-xl font-bold text-white">{ui.title}</h1>
                <p className="text-sm text-gray-500 mt-1 mb-6">Sign in with your work email and 6-digit PIN.</p>
                <Field label="Email">
                  <div className="relative">
                    <Mail className="w-4 h-4 text-gray-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input type="email" autoComplete="username" autoFocus className={`${inputCls()} pl-10 ${ui.ring}`} value={email}
                      onChange={(e) => { setEmail(e.target.value); setErr(""); }} placeholder="name@company.com" />
                  </div>
                </Field>
                <div className="mt-4">
                  <Field label="PIN">
                    <input type="password" inputMode="numeric" autoComplete="current-password" maxLength={6}
                      className={`${inputCls()} tracking-[0.6em] font-mono text-center text-lg ${ui.ring}`} value={pin}
                      onChange={(e) => { setPin(e.target.value.replace(/\D/g, "").slice(0, 6)); setErr(""); }} placeholder="••••••" />
                  </Field>
                </div>
                {err && <p className="text-sm text-red-300 mt-3" role="alert">{err}</p>}
                <Button type="submit" className="w-full mt-6" loading={busy}>Sign in</Button>
                <p className="text-[11px] text-gray-600 mt-4 text-center">
                  5 wrong attempts lock the account for 15 minutes. Forgot your PIN? Ask an Admin to reset it.
                </p>
                <div className="flex justify-center gap-4 mt-4 text-xs">
                  {role !== "ADMIN" && <Link to="/admin/login" className="text-gray-500 hover:text-white">Admin login</Link>}
                  {role !== "SUPPORT" && <Link to="/support/login" className="text-gray-500 hover:text-white">Customer Support login</Link>}
                  <Link to="/signin" className="text-gray-500 hover:text-white">Customer login</Link>
                </div>
              </motion.form>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

function ResetPin({ tempPin, onDone, onCancel, api }) {
  const [current, setCurrent] = useState(tempPin || "");
  const [first, setFirst] = useState("");
  const [pin, setPin] = useState("");
  const [err, setErr] = useState("");
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);

  const complete = async (v) => {
    if (!first) {
      const e = validatePin(v);
      if (e) { setErr(e); setTick((t) => t + 1); setPin(""); return; }
      if (v === current) { setErr("Choose a PIN different from the temporary one."); setTick((t) => t + 1); setPin(""); return; }
      setFirst(v); setPin(""); setErr("");
      return;
    }
    if (v !== first) { setErr("PINs didn't match. Start again."); setTick((t) => t + 1); setFirst(""); setPin(""); return; }
    setBusy(true);
    const r = await api("/security/pin", { method: "POST", body: { current_pin: current, new_pin: v } });
    setBusy(false);
    if (r.ok) onDone();
    else { setErr(r.message); setFirst(""); setPin(""); setTick((t) => t + 1); }
  };

  return (
    <div>
      <div className="w-11 h-11 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-4"><KeyRound className="w-5 h-5 text-amber-300" /></div>
      <h1 className="text-xl font-bold text-white">{first ? "Confirm your new PIN" : "Set your own 6-digit PIN"}</h1>
      <p className="text-sm text-gray-500 mt-1 mb-6">You signed in with a temporary PIN from an Admin. Choose a new one to continue.</p>
      {!tempPin && (
        <div className="mb-5">
          <Field label="Temporary PIN">
            <input type="password" inputMode="numeric" maxLength={6} className={`${inputCls()} tracking-[0.6em] font-mono text-center`} value={current}
              onChange={(e) => setCurrent(e.target.value.replace(/\D/g, "").slice(0, 6))} />
          </Field>
        </div>
      )}
      <PinPad value={pin} onChange={(v) => { setPin(v); setErr(""); }} length={6} onComplete={complete} disabled={busy || current.length !== 6} error={err ? tick : 0} />
      {err && <p className="text-sm text-red-300 text-center mt-4">{err}</p>}
      <Banner tone="warn">Never reuse the temporary PIN, and never share your PIN.</Banner>
      <button onClick={onCancel} className="block mx-auto mt-4 text-xs text-gray-500 hover:text-white">Cancel and sign out</button>
    </div>
  );
}
