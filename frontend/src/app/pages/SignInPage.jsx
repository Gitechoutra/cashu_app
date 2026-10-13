import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { Navigate, useNavigate } from "react-router";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Fingerprint, Home, KeyRound, Smartphone, UserRound } from "lucide-react";
import { publicPost, useAuth } from "../context/AuthContext";
import { Banner, Button, Field, inputCls } from "../components/ui";
import { PinPad } from "../components/PinPad";
import { validateMobile, validateName, validateOtp, validatePin } from "../utils/validation";
import { createCredential, isBiometricAvailable } from "../utils/webauthn";
import { Logo } from "./OnboardingPage";
import { homeFor } from "../utils/roles";

/** Mobile → OTP → (new user) name → PIN → optional biometric → app. */
export function SignInPage() {
  const { status, user, setSession, requireUnlock } = useAuth();
  const [step, setStep] = useState("mobile");
  const [mobile, setMobile] = useState("");
  const [devOtp, setDevOtp] = useState("");   // only set by the dev console SMS provider

  // Resume onboarding for a signed-in user who hasn't finished it.
  const resumed = useRef(false);
  useEffect(() => {
    if (resumed.current || status !== "onboarding" || !user) return;
    resumed.current = true;
    if (!user.full_name) setStep("name");
    else if (!user.has_pin) setStep("pin");
  }, [status, user]);

  if (status === "ready" && step !== "biometric") return <Navigate to={homeFor(user?.role)} replace />;

  return (
    <div className="min-h-screen bg-[#070B14] bg-grid flex flex-col">
      <div className="absolute inset-0 bg-[radial-gradient(60%_40%_at_50%_0%,rgba(34,211,238,0.12),transparent)] pointer-events-none" />
      <header className="relative px-6 pt-8 max-w-md w-full mx-auto flex items-center justify-between">
        <Logo />
        <Link to="/" className="text-xs text-gray-400 hover:text-white inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg hover:bg-white/5">
          <Home className="w-3.5 h-3.5" /> Home
        </Link>
      </header>
      <main className="relative flex-1 flex items-start sm:items-center justify-center px-6 py-10">
        <div className="w-full max-w-md bg-[#0C1220]/90 border border-white/8 rounded-3xl p-6 sm:p-8 shadow-2xl">
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.18 }}>
              {step === "mobile" && <MobileStep mobile={mobile} setMobile={setMobile} onSent={(d) => { setDevOtp(d?.otp_number || ""); setStep("otp"); }} />}
              {step === "otp" && <OtpStep mobile={mobile} devOtp={devOtp} setDevOtp={setDevOtp} onBack={() => setStep("mobile")}
                onVerified={(data) => {
                if (data.requires_unlock) { requireUnlock(data.user); return; }     // returning user: PIN next
                resumed.current = true;
                setSession(data); setStep(!data.user.full_name ? "name" : !data.user.has_pin ? "pin" : "done");
              }} />}
              {step === "name" && <NameStep onDone={() => setStep(user?.has_pin ? "done" : "pin")} />}
              {step === "pin" && <PinStep onDone={() => setStep("biometric")} />}
              {step === "biometric" && <BiometricStep />}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

function Header({ icon: Icon, title, text }) {
  return (
    <div className="mb-6">
      <div className="w-11 h-11 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-4"><Icon className="w-5 h-5 text-cyan-300" /></div>
      <h1 className="text-xl font-bold text-white">{title}</h1>
      <p className="text-sm text-gray-500 mt-1">{text}</p>
    </div>
  );
}

function MobileStep({ mobile, setMobile, onSent }) {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    const v = validateMobile(mobile);
    setErr(v);
    if (v || busy) return;
    setBusy(true);
    const r = await publicPost("/authentication/otp/send", { mobile_number: mobile });
    setBusy(false);
    if (r.ok) onSent(r.data);
    // A code was already sent moments ago — continue to the code screen instead of a dead end.
    else if (r.code === "OTP_COOLDOWN") onSent({ resend_after: r.data.retry_after });
    else setErr(r.message);
  };
  return (
    <form onSubmit={submit} noValidate>
      <Header icon={Smartphone} title="Sign in or create account" text="We'll send a one-time code to your mobile number." />
      <Field label="Mobile number" error={err}>
        <div className="flex">
          <span className="px-3.5 flex items-center rounded-l-xl border border-r-0 border-white/10 bg-white/5 text-sm text-gray-400">+91</span>
          <input className={`${inputCls(err)} rounded-l-none`} inputMode="numeric" autoComplete="tel-national" autoFocus
            value={mobile} onChange={(e) => { setMobile(e.target.value.replace(/[^\d]/g, "").slice(0, 10)); setErr(""); }} placeholder="98765 43210" />
        </div>
      </Field>
      <Button type="submit" className="w-full mt-6" loading={busy}>Send OTP</Button>
    </form>
  );
}

function OtpStep({ mobile, devOtp, setDevOtp, onBack, onVerified }) {
  const [otp, setOtp] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [wait, setWait] = useState(30);
  const inputs = useRef([]);
  const once = useRef(false);

  useEffect(() => {
    const t = setInterval(() => setWait((w) => (w > 0 ? w - 1 : 0)), 1000);
    inputs.current[0]?.focus();
    return () => clearInterval(t);
  }, []);

  const verify = async (code) => {
    if (validateOtp(code) || busy || once.current) return;
    once.current = true;
    setBusy(true);
    const r = await publicPost("/authentication/otp/verify", { mobile_number: mobile, otp_code: code });
    setBusy(false);
    once.current = false;
    if (r.ok) onVerified(r.data);
    else if (r.code === "USE_STAFF_LOGIN") setErr("This is a staff account. Use the Admin or Customer Support login (email + PIN).");
    else { setErr(r.message); setOtp(""); inputs.current[0]?.focus(); }
  };

  const setDigit = (i, d) => {
    const chars = otp.padEnd(6, " ").split("");
    chars[i] = d || " ";
    const next = chars.join("").replace(/\s+$/, "");
    setOtp(next); setErr("");
    if (d && i < 5) inputs.current[i + 1]?.focus();
    if (next.replace(/\s/g, "").length === 6) verify(next);
  };

  const onPaste = (e) => {
    const d = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (d.length === 6) { e.preventDefault(); setOtp(d); verify(d); }
  };

  const resend = async () => {
    const r = await publicPost("/authentication/otp/send", { mobile_number: mobile });
    if (r.ok) { setWait(r.data.resend_after || 30); setErr(""); setDevOtp(r.data.otp_number || ""); }
    else if (r.code === "OTP_COOLDOWN") setWait(r.data.retry_after || 30);
    else setErr(r.message);
  };

  return (
    <div>
      <button onClick={onBack} className="text-gray-500 hover:text-white mb-4 flex items-center gap-1 text-xs"><ArrowLeft className="w-3.5 h-3.5" /> Change number</button>
      <Header icon={KeyRound} title="Enter the code" text={`Sent to +91 ${mobile.slice(0, 5)} ${mobile.slice(5)}`} />
      <div className="flex gap-2 justify-between" onPaste={onPaste}>
        {Array.from({ length: 6 }).map((_, i) => (
          <input key={i} ref={(el) => (inputs.current[i] = el)} inputMode="numeric" autoComplete={i === 0 ? "one-time-code" : "off"}
            maxLength={1} value={(otp[i] || "").trim()} disabled={busy} aria-label={`Digit ${i + 1}`}
            onChange={(e) => setDigit(i, e.target.value.replace(/\D/g, "").slice(-1))}
            onKeyDown={(e) => { if (e.key === "Backspace" && !(otp[i] || "").trim() && i > 0) inputs.current[i - 1]?.focus(); }}
            className={`w-12 h-14 text-center text-xl font-semibold rounded-xl bg-[#141C30] border ${err ? "border-red-500/50" : "border-white/10"} text-white focus:outline-none focus:border-cyan-500/60`} />
        ))}
      </div>
      {devOtp && (
        <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-xs text-amber-100">
          <span>Development OTP (no SMS provider configured): <b className="font-mono tracking-widest text-sm">{devOtp}</b></span>
          <button type="button" onClick={() => { setOtp(devOtp); verify(devOtp); }} className="shrink-0 px-2.5 py-1 rounded-lg bg-amber-500/15 text-amber-200 hover:bg-amber-500/25">Fill</button>
        </div>
      )}
      {err && <p className="text-sm text-red-300 mt-3">{err}</p>}
      {err.startsWith("This is a staff account") && (
        <div className="flex gap-3 mt-2 text-xs"><a href="/admin/login" className="text-amber-300">Admin login</a><a href="/support/login" className="text-violet-300">Customer Support login</a></div>
      )}
      <div className="flex items-center justify-between mt-6">
        <button onClick={resend} disabled={wait > 0} className="text-sm text-cyan-300 disabled:text-gray-600">
          {wait > 0 ? `Resend in ${wait}s` : "Resend OTP"}
        </button>
        <Button onClick={() => verify(otp)} loading={busy} disabled={otp.replace(/\s/g, "").length !== 6}>Verify</Button>
      </div>
    </div>
  );
}

function NameStep({ onDone }) {
  const { api, setUser } = useAuth();
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    const v = validateName(name);
    setErr(v);
    if (v || busy) return;
    setBusy(true);
    const r = await api("/authentication/me", { method: "PATCH", body: { full_name: name.trim() } });
    setBusy(false);
    if (r.ok) { setUser(r.data); onDone(); } else setErr(r.message);
  };
  return (
    <form onSubmit={submit} noValidate>
      <Header icon={UserRound} title="What should we call you?" text="Your name is shown in the app only." />
      <Field label="Full name" error={err}>
        <input className={inputCls(err)} value={name} autoFocus maxLength={100} autoComplete="name"
          onChange={(e) => { setName(e.target.value); setErr(""); }} placeholder="e.g. Asha Rao" />
      </Field>
      <Button type="submit" className="w-full mt-6" loading={busy}>Continue</Button>
    </form>
  );
}

function PinStep({ onDone }) {
  const { api, setUser, user } = useAuth();
  const [first, setFirst] = useState("");
  const [pin, setPin] = useState("");
  const [err, setErr] = useState("");
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);

  const complete = async (v) => {
    if (!first) {
      const e = validatePin(v);
      if (e) { setErr(e); setTick((t) => t + 1); setPin(""); return; }
      setFirst(v); setPin(""); setErr("");
      return;
    }
    if (v !== first) { setErr("PINs didn't match. Start again."); setTick((t) => t + 1); setFirst(""); setPin(""); return; }
    setBusy(true);
    const r = await api("/security/pin", { method: "POST", body: { new_pin: v } });
    setBusy(false);
    if (r.ok) { setUser({ ...user, has_pin: true }); onDone(); }
    else { setErr(r.message); setFirst(""); setPin(""); }
  };

  return (
    <div>
      <Header icon={KeyRound} title={first ? "Confirm your app PIN" : "Set a 4-digit app PIN"}
        text="You'll use it to unlock CardVault on this device. Avoid 1234, 1111 and your birth year." />
      <PinPad value={pin} onChange={(v) => { setPin(v); setErr(""); }} length={4} onComplete={complete} disabled={busy} error={err ? tick : 0} />
      {err && <p className="text-sm text-red-300 text-center mt-4">{err}</p>}
    </div>
  );
}

function BiometricStep() {
  const { api, finishOnboarding, user } = useAuth();
  const nav = useNavigate();
  const [available, setAvailable] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { isBiometricAvailable().then(setAvailable); }, []);
  const finish = () => { finishOnboarding({ has_pin: true }); nav(homeFor(user?.role), { replace: true }); };

  useEffect(() => { if (available === false) finish(); }, [available]); // eslint-disable-line react-hooks/exhaustive-deps

  const enable = async () => {
    setBusy(true); setErr("");
    const o = await api("/security/webauthn/register/options", { method: "POST" });
    if (!o.ok) { setBusy(false); setErr(o.message); return; }
    try {
      const credential = await createCredential(o.data.options);
      const r = await api("/security/webauthn/register/verify", { method: "POST", body: { credential, label: navigator.platform || "This device" } });
      if (!r.ok) throw new Error(r.message);
      finishOnboarding({ has_pin: true, biometric_enabled: true });
      nav(homeFor(user?.role), { replace: true });
    } catch (e) {
      setErr(e?.message && !e.name?.includes("NotAllowed") ? e.message : "Biometric setup was cancelled.");
    } finally { setBusy(false); }
  };

  if (available === null) return null;
  return (
    <div>
      <Header icon={Fingerprint} title="Unlock with fingerprint or face?" text="Use your device's biometrics instead of typing your PIN. Your biometric data never leaves your device." />
      {err && <div className="mb-4"><Banner tone="error">{err}</Banner></div>}
      <div className="flex gap-2">
        <Button variant="ghost" className="flex-1" onClick={finish} disabled={busy}>Not now</Button>
        <Button className="flex-1" onClick={enable} loading={busy}>Enable</Button>
      </div>
    </div>
  );
}
