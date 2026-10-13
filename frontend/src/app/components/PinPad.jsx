import { useEffect } from "react";
import { motion } from "motion/react";
import { Delete, Fingerprint } from "lucide-react";

/* Short viewports (landscape phones, small laptops) get a tighter keypad via
   [@media(max-height:680px)] classes — written out literally so Tailwind generates them. */

/** Numeric PIN entry with on-screen keypad + physical keyboard support. */
export function PinPad({ value, onChange, length = 4, onComplete, disabled, error, onBiometric }) {
  useEffect(() => {
    const onKey = (e) => {
      if (disabled) return;
      if (/^\d$/.test(e.key)) press(e.key);
      else if (e.key === "Backspace") onChange(value.slice(0, -1));
      else if (e.key === "Enter" && value.length >= 4) onComplete?.(value);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const press = (d) => {
    if (disabled || value.length >= length) return;
    const next = value + d;
    onChange(next);
    if (next.length === length) onComplete?.(next);
  };

  return (
    // w-full: without it a centred flex parent shrinks the pad to the width of the dots.
    <div className="w-full flex flex-col items-center">
      <motion.div className={`flex gap-4 mb-8 sm:mb-10 [@media(max-height:680px)]:mb-5`} role="status" aria-label={`${value.length} of ${length} digits entered`}
        animate={error ? { x: [0, -10, 10, -6, 6, 0] } : {}} transition={{ duration: 0.35 }} key={error ? `e${error}` : "ok"}>
        {Array.from({ length }).map((_, i) => (
          <span key={i} className={`w-3.5 h-3.5 sm:w-4 sm:h-4 rounded-full border-2 transition-all duration-150 ${
            i < value.length ? (error ? "bg-red-400 border-red-400" : "bg-cyan-400 border-cyan-400 scale-110") : "border-white/30"}`} />
        ))}
      </motion.div>

      <div className={`grid grid-cols-3 justify-items-center gap-x-6 gap-y-4 sm:gap-x-8 sm:gap-y-5 [@media(max-height:680px)]:gap-y-2.5 [@media(max-height:680px)]:gap-x-5`}>
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => <Key key={d} onClick={() => press(d)} disabled={disabled}>{d}</Key>)}
        {onBiometric ? (
          <Key onClick={onBiometric} disabled={disabled} label="Use biometrics" plain><Fingerprint className="w-7 h-7 text-cyan-300" /></Key>
        ) : <span aria-hidden />}
        <Key onClick={() => press("0")} disabled={disabled}>0</Key>
        <Key onClick={() => onChange(value.slice(0, -1))} disabled={disabled || !value} label="Delete" plain><Delete className="w-6 h-6" /></Key>
      </div>
    </div>
  );
}

function Key({ children, onClick, disabled, label, plain }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={label}
      className={`w-[68px] h-[68px] sm:w-[76px] sm:h-[76px] [@media(max-height:680px)]:w-14 [@media(max-height:680px)]:h-14 rounded-full
        flex items-center justify-center text-2xl sm:text-[26px] [@media(max-height:680px)]:text-xl font-semibold text-white
        select-none touch-manipulation transition active:scale-90 disabled:opacity-40
        focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60
        ${plain ? "text-gray-300 hover:bg-white/[0.06]" : "bg-white/[0.05] border border-white/[0.07] hover:bg-white/[0.10] active:bg-white/[0.14]"}`}>
      {children}
    </button>
  );
}
