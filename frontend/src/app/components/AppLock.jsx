import { useEffect, useRef, useState } from "react";
import { LockKeyhole } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { isBiometricAvailable } from "../utils/webauthn";
import { PinPad } from "./PinPad";
import { isStaff, pinLengthFor } from "../utils/roles";

/** Full-screen lock shown on app open and after idle/background timeout. */
export function AppLock() {
  const { lockInfo, unlockWithPin, unlockWithBiometric, logout } = useAuth();
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [errTick, setErrTick] = useState(0);
  const [bioOk, setBioOk] = useState(false);
  const autoTried = useRef(false);

  const bio = async () => {
    setBusy(true); setMsg("");
    const r = await unlockWithBiometric();
    setBusy(false);
    if (!r.ok) setMsg(r.message);
  };

  useEffect(() => {
    (async () => {
      const ok = !!lockInfo?.biometric_enabled && (await isBiometricAvailable());
      setBioOk(ok);
      if (ok && !autoTried.current) { autoTried.current = true; bio(); }
    })();
  }, [lockInfo]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (value) => {
    if (busy || value.length < 4) return;
    setBusy(true); setMsg("");
    const r = await unlockWithPin(value);
    setBusy(false);
    if (!r.ok) {
      setPin(""); setErrTick((t) => t + 1);
      setMsg(r.data?.attempts_remaining !== undefined ? `Incorrect PIN · ${r.data.attempts_remaining} attempt(s) left` : r.message);
    }
  };

  const name = lockInfo?.full_name?.split(" ")[0];
  return (
    <div className="fixed inset-0 z-[100] bg-[#070B14] bg-grid overflow-y-auto overscroll-contain">
      <div className="fixed inset-0 bg-[radial-gradient(60%_40%_at_50%_0%,rgba(34,211,238,0.12),transparent)] pointer-events-none" />
      {/* min-h-full + justify-center: centred on tall screens, scrollable (never clipped) on short ones. */}
      <div className="relative min-h-full w-full flex flex-col items-center justify-center px-5 sm:px-6
                      pt-[max(2rem,env(safe-area-inset-top))] pb-[max(2rem,env(safe-area-inset-bottom))]
                      [@media(max-height:680px)]:pt-5 [@media(max-height:680px)]:pb-5">
        <div className="w-full max-w-sm flex flex-col items-center text-center">
          <div className="w-14 h-14 sm:w-16 sm:h-16 [@media(max-height:680px)]:w-11 [@media(max-height:680px)]:h-11 rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 mb-5 [@media(max-height:680px)]:mb-3">
            <LockKeyhole className="w-6 h-6 sm:w-7 sm:h-7 [@media(max-height:680px)]:w-5 [@media(max-height:680px)]:h-5 text-white" />
          </div>
          <h1 className="text-xl sm:text-2xl [@media(max-height:680px)]:text-lg font-bold text-white break-words">
            {name ? `Welcome back, ${name}` : "Welcome back"}
          </h1>
          <p className="text-sm text-gray-500 mt-1.5 mb-8 sm:mb-10 [@media(max-height:680px)]:mb-5">
            <span className="block sm:inline">Enter your app PIN to unlock</span>
            <span className="hidden sm:inline"> · </span>
            <span className="block sm:inline text-gray-600 sm:text-gray-500">{lockInfo?.mobile_number}</span>
          </p>
          <PinPad value={pin} onChange={(v) => { setPin(v); setMsg(""); }} length={pinLengthFor(lockInfo?.role)} onComplete={submit}
            disabled={busy} error={msg ? errTick : 0} onBiometric={bioOk ? bio : undefined} />
          <div className="min-h-[2.5rem] mt-4 [@media(max-height:680px)]:mt-2 flex items-center justify-center" aria-live="assertive">
            {msg && <p className="text-sm text-red-300">{msg}</p>}
          </div>
          <button onClick={logout} className="text-sm text-gray-500 hover:text-white py-2 px-3 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/40">
            {isStaff(lockInfo?.role) ? "Not you? Sign in again" : "Not you? Sign in with OTP"}
          </button>
        </div>
      </div>
    </div>
  );
}
