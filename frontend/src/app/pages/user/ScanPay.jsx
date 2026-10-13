import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  AlertTriangle, CameraOff, CheckCircle2, Copy, ExternalLink, ImageUp, Info, Link2, ScanLine, ShieldCheck,
  Smartphone, Zap, ZapOff,
} from "lucide-react";
import jsQR from "jsqr";
import { Banner, Button, Field, inputCls, useToast } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";
import { buildUpiLink, classifyQr, isValidUpiAmount } from "../../utils/upi";
import { fmtINR } from "../../utils/format";

/**
 * Scan & Pay (like CRED / PhonePe scan): reads a UPI QR with the camera or from
 * an image, shows who you're paying, and hands the payment to a UPI app on the
 * device. CardVault itself does not move UPI money — that requires NPCI
 * approval as a UPI app (TPAP) with a sponsor bank.
 */
export function ScanPay() {
  const toast = useToast();
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const rafRef = useRef(null);
  const detectorRef = useRef(null);
  const [camState, setCamState] = useState("idle");     // idle | starting | scanning | denied | unavailable | insecure
  const [result, setResult] = useState(null);
  const [torch, setTorch] = useState({ supported: false, on: false });

  const stop = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const onDecoded = useCallback((text) => {
    stop();
    if (navigator.vibrate) navigator.vibrate(40);
    setResult(classifyQr(text));
    setCamState("idle");
  }, [stop]);

  const tick = useCallback(async () => {
    const v = videoRef.current;
    if (!v || !streamRef.current) return;
    if (v.readyState >= 2) {
      try {
        if (detectorRef.current) {
          const codes = await detectorRef.current.detect(v);
          if (codes[0]?.rawValue) return onDecoded(codes[0].rawValue);
        } else {
          const c = canvasRef.current;
          const w = Math.min(v.videoWidth, 720), h = Math.round((v.videoHeight / v.videoWidth) * w);
          c.width = w; c.height = h;
          const ctx = c.getContext("2d", { willReadFrequently: true });
          ctx.drawImage(v, 0, 0, w, h);
          const code = jsQR(ctx.getImageData(0, 0, w, h).data, w, h, { inversionAttempts: "dontInvert" });
          if (code?.data) return onDecoded(code.data);
        }
      } catch { /* keep scanning */ }
    }
    rafRef.current = requestAnimationFrame(tick);
  }, [onDecoded]);

  const start = useCallback(async () => {
    setResult(null);
    if (!window.isSecureContext) { setCamState("insecure"); return; }
    if (!navigator.mediaDevices?.getUserMedia) { setCamState("unavailable"); return; }
    setCamState("starting");
    // The camera view may still be animating in — wait (≤1.5s) for its <video>.
    for (let i = 0; i < 30 && !videoRef.current; i++) await new Promise((r) => setTimeout(r, 50));
    if (!videoRef.current) { setCamState("idle"); return; }
    try {
      if ("BarcodeDetector" in window) {
        const formats = await window.BarcodeDetector.getSupportedFormats?.();
        if (!formats || formats.includes("qr_code")) detectorRef.current = new window.BarcodeDetector({ formats: ["qr_code"] });
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false,
      });
      streamRef.current = stream;
      const track = stream.getVideoTracks()[0];
      setTorch({ supported: !!track.getCapabilities?.().torch, on: false });
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setCamState("scanning");
      rafRef.current = requestAnimationFrame(tick);
    } catch (e) {
      stop();
      setCamState(e?.name === "NotAllowedError" ? "denied" : "unavailable");
    }
  }, [tick, stop]);

  const [scanRequest, setScanRequest] = useState(1);
  const scanAgain = () => { setResult(null); setScanRequest((n) => n + 1); };
  useEffect(() => { if (!result && scanRequest) start(); }, [scanRequest]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => stop, [stop]);
  useEffect(() => {
    const onHide = () => { if (document.hidden) { stop(); setCamState("idle"); } };
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, [stop]);

  const toggleTorch = async () => {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track) return;
    try { await track.applyConstraints({ advanced: [{ torch: !torch.on }] }); setTorch((t) => ({ ...t, on: !t.on })); }
    catch { toast("error", "Torch isn't available on this camera."); }
  };

  const fromImage = async (file) => {
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 8 * 1024 * 1024) { toast("error", "Choose an image under 8 MB."); return; }
    stop();
    try {
      const bmp = await createImageBitmap(file);
      const scale = Math.min(1, 1280 / Math.max(bmp.width, bmp.height));
      const w = Math.round(bmp.width * scale), h = Math.round(bmp.height * scale);
      const c = canvasRef.current; c.width = w; c.height = h;
      const ctx = c.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(bmp, 0, 0, w, h);
      const code = jsQR(ctx.getImageData(0, 0, w, h).data, w, h, { inversionAttempts: "attemptBoth" });
      if (code?.data) onDecoded(code.data);
      else { toast("error", "No QR code found in that image."); setCamState("idle"); }
    } catch { toast("error", "Couldn't read that image."); }
  };

  return (
    <div className="p-4 lg:p-8 max-w-xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2"><ScanLine className="w-5 h-5 text-cyan-300" /> Scan & Pay</h1>
        <p className="text-sm text-gray-500">Scan any UPI QR code to pay from your UPI app.</p>
      </div>

      <AnimatePresence mode="wait">
        {!result ? (
          <motion.div key="cam" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
            <div className="relative aspect-square w-full max-w-sm mx-auto rounded-3xl overflow-hidden bg-black ring-1 ring-white/10">
              <video ref={videoRef} playsInline muted className={`w-full h-full object-cover ${camState === "scanning" ? "" : "opacity-0"}`} />
              {camState === "scanning" && (
                <>
                  <div className="absolute inset-[14%] pointer-events-none">
                    <div className="absolute inset-0 rounded-2xl" style={{ boxShadow: "0 0 0 9999px rgba(0,0,0,0.45)" }} />
                    {["top-0 left-0 border-t-4 border-l-4 rounded-tl-2xl", "top-0 right-0 border-t-4 border-r-4 rounded-tr-2xl",
                      "bottom-0 left-0 border-b-4 border-l-4 rounded-bl-2xl", "bottom-0 right-0 border-b-4 border-r-4 rounded-br-2xl"]
                      .map((c) => <span key={c} className={`absolute w-10 h-10 border-cyan-400 ${c}`} />)}
                    <motion.div className="absolute left-3 right-3 h-0.5 bg-gradient-to-r from-transparent via-cyan-300 to-transparent shadow-[0_0_12px_rgba(34,211,238,0.8)]"
                      initial={{ top: "6%" }} animate={{ top: ["6%", "94%", "6%"] }} transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }} />
                  </div>
                  {torch.supported && (
                    <button onClick={toggleTorch} aria-label="Toggle torch"
                      className="absolute bottom-4 right-4 w-11 h-11 rounded-full bg-black/60 border border-white/20 flex items-center justify-center text-white">
                      {torch.on ? <ZapOff className="w-5 h-5" /> : <Zap className="w-5 h-5" />}
                    </button>
                  )}
                </>
              )}
              {camState !== "scanning" && <CameraMessage state={camState} onRetry={start} />}
            </div>
            <p className="text-center text-xs text-gray-500">Point your camera at a UPI QR code — it scans automatically.</p>
            <label className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200 hover:bg-white/10 cursor-pointer">
              <ImageUp className="w-4 h-4" /> Upload QR from gallery
              <input type="file" accept="image/*" className="hidden" onChange={(e) => { fromImage(e.target.files?.[0]); e.target.value = ""; }} />
            </label>
          </motion.div>
        ) : (
          <motion.div key="res" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <ScanResult result={result} onScanAgain={scanAgain} />
          </motion.div>
        )}
      </AnimatePresence>

      <canvas ref={canvasRef} className="hidden" />
      {!result && <RecentPayees />}
      <div className="flex items-start gap-2 text-[11px] text-gray-500">
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>CardVault reads the QR and opens your UPI app (Google Pay, PhonePe, CRED, BHIM…) to complete the payment.
          UPI payments inside CardVault need NPCI approval as a UPI app and aren't enabled yet.</span>
      </div>
    </div>
  );
}

function CameraMessage({ state, onRetry }) {
  const msg = {
    idle: ["Camera paused", "Tap below to start scanning."],
    starting: ["Starting camera…", "Allow camera access when your browser asks."],
    denied: ["Camera permission denied", "Allow camera access in your browser's site settings, or upload a QR image."],
    unavailable: ["No camera available", "This device or browser can't open a camera. Upload a QR image instead."],
    insecure: ["Camera needs HTTPS", "Open the app over https:// (or localhost) to use the camera."],
  }[state] || ["", ""];
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6">
      {state === "starting" ? <ScanLine className="w-8 h-8 text-cyan-300 animate-pulse" /> : <CameraOff className="w-8 h-8 text-gray-500" />}
      <div className="text-sm text-white font-medium mt-3">{msg[0]}</div>
      <div className="text-xs text-gray-400 mt-1 max-w-[16rem]">{msg[1]}</div>
      {state !== "starting" && state !== "insecure" && <Button size="sm" variant="ghost" className="mt-4" onClick={onRetry}>Start camera</Button>}
    </div>
  );
}

function ScanResult({ result, onScanAgain }) {
  const toast = useToast();
  const { api } = useAuth();
  const [amount, setAmount] = useState("");
  const [err, setErr] = useState("");
  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

  if (result.kind === "upi") {
    const p = result.payee;
    const pay = () => {
      if (!p.amount && !isValidUpiAmount(amount)) { setErr("Enter a valid amount (up to 2 decimals)."); return; }
      const link = buildUpiLink(result, p.amount ? null : amount);
      if (!link) { setErr("Couldn't prepare this payment."); return; }
      // Record the hand-off for "Recent payees" (best effort; never blocks paying).
      api("/scan/payments", { method: "POST", body: { payee_vpa: p.vpa, payee_name: p.name, merchant_code: p.merchantCode,
        amount: p.amount || amount || null, note: p.note } }).catch(() => {});
      window.location.href = link;      // the OS shows the installed UPI apps
    };
    const initials = (p.name || p.vpa).split(/[\s@.]/).filter(Boolean).slice(0, 2).map((s) => s[0]).join("").toUpperCase();
    return (
      <div className="space-y-4">
        <div className="bg-[#0C1220] border border-white/5 rounded-3xl p-6 text-center">
          <div className="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-cyan-500/30 to-blue-600/30 border border-white/10 flex items-center justify-center text-lg font-bold text-white">{initials}</div>
          <div className="text-xs text-gray-500 mt-4">Paying</div>
          <div className="text-lg font-semibold text-white break-words">{p.name || "Unnamed payee"}</div>
          <div className="text-sm text-gray-400 font-mono break-all">{p.vpa}</div>
          <div className="flex items-center justify-center gap-2 mt-2">
            {p.merchantCode && <span className="text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30 text-emerald-300">Merchant</span>}
            {!p.name && <span className="text-[10px] px-2 py-0.5 rounded-full border border-amber-500/30 text-amber-300">No name in QR</span>}
          </div>
          {p.amount ? (
            <div className="text-3xl font-bold text-white mt-5">{fmtINR(p.amount)}</div>
          ) : (
            <div className="mt-5 text-left">
              <Field label="Amount (₹)" error={err}>
                <input className={`${inputCls(err)} text-2xl font-bold text-center`} inputMode="decimal" autoFocus placeholder="0"
                  value={amount} onChange={(e) => { setAmount(e.target.value.replace(/[^\d.]/g, "")); setErr(""); }} />
              </Field>
            </div>
          )}
          {p.note && <div className="text-xs text-gray-500 mt-3">Note: {p.note}</div>}
        </div>

        <Banner tone="warn" icon={ShieldCheck}>Check the payee name and UPI ID before paying. Your UPI app will ask for your UPI PIN — never share it, and never scan a QR to <i>receive</i> money.</Banner>

        {isMobile ? (
          <Button className="w-full" onClick={pay}><Smartphone className="w-4 h-4" /> Pay with UPI app</Button>
        ) : (
          <div className="space-y-2">
            <Banner icon={Smartphone}>UPI apps open on your phone. Scan this code with your phone's UPI app, or copy the UPI ID.</Banner>
            <Button variant="ghost" className="w-full" onClick={() => navigator.clipboard?.writeText(p.vpa).then(() => toast("success", "UPI ID copied."))}>
              <Copy className="w-4 h-4" /> Copy UPI ID
            </Button>
          </div>
        )}
        <Button variant="ghost" className="w-full" onClick={onScanAgain}><ScanLine className="w-4 h-4" /> Scan another code</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-[#0C1220] border border-white/5 rounded-3xl p-6">
        {result.kind === "invalid-upi" ? (
          <div className="text-center">
            <AlertTriangle className="w-10 h-10 text-amber-300 mx-auto" />
            <div className="text-white font-semibold mt-3">Not a valid UPI payment code</div>
            <p className="text-sm text-gray-400 mt-1">{result.reason} Don't pay using this code.</p>
          </div>
        ) : result.kind === "url" ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-white font-semibold"><Link2 className="w-4 h-4 text-cyan-300" /> This QR contains a link</div>
            <div className="text-sm text-gray-300 break-all font-mono bg-white/5 rounded-xl p-3">{result.url}</div>
            <Banner tone="warn" icon={AlertTriangle}>Only open links you trust. Opens <b>{result.host}</b> in a new tab — CardVault never asks for your PIN, OTP or card details on other sites.</Banner>
            <a href={result.url} target="_blank" rel="noopener noreferrer nofollow"
              className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200 hover:bg-white/10">
              Open {result.host} <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-white font-semibold"><CheckCircle2 className="w-4 h-4 text-cyan-300" /> QR scanned</div>
            <div className="text-sm text-gray-300 break-words whitespace-pre-wrap bg-white/5 rounded-xl p-3">{result.text || "(empty)"}</div>
            <p className="text-xs text-gray-500">This isn't a UPI payment code.</p>
            <Button variant="ghost" size="sm" onClick={() => navigator.clipboard?.writeText(result.text).then(() => toast("success", "Copied."))}><Copy className="w-3.5 h-3.5" /> Copy text</Button>
          </div>
        )}
      </div>
      <Button className="w-full" onClick={onScanAgain}><ScanLine className="w-4 h-4" /> Scan again</Button>
    </div>
  );
}

function RecentPayees() {
  const { api } = useAuth();
  const [rows, setRows] = useState(null);
  useEffect(() => { api("/scan/payments").then((r) => r.ok && setRows(r.data.payments)); }, [api]);
  if (!rows || rows.length === 0) return null;
  return (
    <section className="bg-[#0C1220] border border-white/5 rounded-2xl p-4">
      <h2 className="text-xs text-gray-500 mb-2">Recent payees</h2>
      <ul className="divide-y divide-white/5">
        {rows.slice(0, 5).map((r) => (
          <li key={r.id} className="py-2 flex items-center justify-between gap-3 text-sm">
            <div className="min-w-0">
              <div className="text-white truncate">{r.payee_name || r.payee_vpa}</div>
              <div className="text-[11px] text-gray-500 font-mono truncate">{r.payee_vpa}</div>
            </div>
            <div className="text-right shrink-0">
              <div className="text-gray-200">{r.amount ? fmtINR(r.amount) : "—"}</div>
              <div className="text-[10px] text-gray-600">Opened in UPI app</div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
