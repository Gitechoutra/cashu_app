import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { AnimatePresence, motion } from "motion/react";
import { BellRing, ChevronRight, CreditCard, Headset, ShieldCheck, UserRound } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui";
import { homeFor } from "../utils/roles";

const SLIDES = [
  { icon: CreditCard, title: "All your credit cards. One place.",
    text: "Track limits, balances, utilisation and due dates across every bank — at a glance." },
  { icon: BellRing, title: "Never miss a due date.",
    text: "See what's due and when, and pay your bills securely in a couple of taps." },
  { icon: ShieldCheck, title: "Private by design.",
    text: "We never ask for your full card number, CVV or bank password. Your app is locked with a PIN or your fingerprint." },
];

export function OnboardingPage() {
  const { status, user } = useAuth();
  const nav = useNavigate();
  const [i, setI] = useState(0);
  if (status === "ready") return <Navigate to={homeFor(user?.role)} replace />;
  if (status === "onboarding") return <Navigate to="/signin" replace />;

  const S = SLIDES[i];
  const last = i === SLIDES.length - 1;
  return (
    <div className="min-h-screen bg-[#070B14] bg-grid flex flex-col">
      <div className="absolute inset-0 bg-[radial-gradient(70%_50%_at_50%_0%,rgba(34,211,238,0.14),transparent)] pointer-events-none" />
      <header className="relative px-6 pt-8 flex items-center justify-between max-w-5xl w-full mx-auto">
        <Logo />
        <button onClick={() => nav("/signin")} className="text-sm text-gray-400 hover:text-white">Skip</button>
      </header>

      <main className="relative flex-1 flex flex-col lg:flex-row items-center justify-center gap-10 px-6 max-w-5xl w-full mx-auto">
        <HeroCards />
        <div className="w-full max-w-md">
          <AnimatePresence mode="wait">
            <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.25 }}>
              <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center mb-5">
                <S.icon className="w-5 h-5 text-cyan-300" />
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-white leading-tight tracking-tight">{S.title}</h1>
              <p className="text-gray-400 mt-3 leading-relaxed">{S.text}</p>
            </motion.div>
          </AnimatePresence>
          <div className="flex gap-1.5 mt-8">
            {SLIDES.map((_, k) => (
              <button key={k} onClick={() => setI(k)} aria-label={`Slide ${k + 1}`}
                className={`h-1.5 rounded-full transition-all ${k === i ? "w-8 bg-cyan-400" : "w-3 bg-white/15"}`} />
            ))}
          </div>
          <Button className="w-full mt-8" onClick={() => (last ? nav("/signin") : setI(i + 1))}>
            {last ? "Get started" : "Next"}
          </Button>
          <p className="text-[11px] text-gray-600 mt-4 text-center">By continuing you agree to the Terms and Privacy Policy.</p>
          <LoginChoices />
        </div>
      </main>
    </div>
  );
}

export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
        <CreditCard className="w-4 h-4 text-white" />
      </div>
      <span className="font-bold text-white tracking-tight">CardVault</span>
    </div>
  );
}

function HeroCards() {
  const cards = [
    { g: ["#0F3D7A", "#071E3D"], r: -8, y: 0 },
    { g: ["#97144D", "#4A0726"], r: 4, y: 26 },
    { g: ["#1A4F9C", "#0B2A5B"], r: -2, y: 52 },
  ];
  return (
    <div className="relative w-72 h-60 sm:w-80 sm:h-64 shrink-0" aria-hidden>
      {cards.map((c, k) => (
        <motion.div key={k} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: c.y, rotate: c.r }} transition={{ delay: 0.1 * k, duration: 0.5 }}
          className="card-sheen absolute inset-x-0 mx-auto w-64 sm:w-72 aspect-[1.586] rounded-2xl ring-1 ring-white/10 shadow-2xl shadow-black/50 p-5"
          style={{ background: `linear-gradient(135deg, ${c.g[0]}, ${c.g[1]})` }}>
          <div className="w-10 h-7 rounded-md bg-gradient-to-br from-amber-200 to-amber-400/80" />
          <div className="absolute bottom-5 left-5 font-mono tracking-[0.2em] text-white/80">•••• •••• •••• {["4242", "8810", "1007"][k]}</div>
        </motion.div>
      ))}
    </div>
  );
}

/** Separate sign-in entry points: customers (mobile + OTP) and staff (email + PIN). */
function LoginChoices() {
  const items = [
    { to: "/signin", icon: UserRound, title: "User", text: "Mobile number + OTP", tone: "text-cyan-300 bg-cyan-500/10 border-cyan-500/20" },
    { to: "/admin/login", icon: ShieldCheck, title: "Admin", text: "Email + PIN", tone: "text-amber-300 bg-amber-500/10 border-amber-500/20" },
    { to: "/support/login", icon: Headset, title: "Customer Support", text: "Email + PIN", tone: "text-violet-300 bg-violet-500/10 border-violet-500/20" },
  ];
  return (
    <div className="mt-8">
      <div className="text-[11px] uppercase tracking-[0.18em] text-gray-500 mb-3">Sign in as</div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {items.map((i) => (
          <Link key={i.to} to={i.to}
            className="group flex sm:flex-col items-center sm:items-start gap-3 sm:gap-2 rounded-2xl border border-white/8 bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/15 p-3 transition-colors">
            <span className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ${i.tone}`}><i.icon className="w-4 h-4" /></span>
            <span className="flex-1 min-w-0">
              <span className="block text-sm font-semibold text-white">{i.title}</span>
              <span className="block text-[11px] text-gray-500">{i.text}</span>
            </span>
            <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-gray-300 sm:hidden" />
          </Link>
        ))}
      </div>
    </div>
  );
}
