import { useState } from "react";
import { Landmark } from "lucide-react";

/**
 * Circular bank symbol (PhonePe-style). Icons are bank symbols cut from each
 * bank's official logo and served from /public/banks — no runtime calls to
 * third-party logo services. To add or update a bank, drop a square PNG of its
 * official symbol into public/banks/<code>.png and list it below.
 * Banks without an icon show a neutral bank glyph.
 */
const ICONS = new Set([
  "AMEX", "AU", "AXIS", "BANDHAN", "BOB", "BOM", "CSB", "HDFC", "HSBC", "ICICI", "IDBI", "IDFC",
  "INDUSIND", "IOB", "KOTAK", "KTK", "KVB", "PNB", "RBL", "SBI", "SBM", "SC", "UNION", "YES",
]);

const SIZES = {
  xs: { box: "w-7 h-7", pad: "p-1", glyph: "w-3.5 h-3.5" },
  sm: { box: "w-9 h-9", pad: "p-1.5", glyph: "w-4 h-4" },
  md: { box: "w-11 h-11", pad: "p-2", glyph: "w-5 h-5" },
  lg: { box: "w-16 h-16", pad: "p-3", glyph: "w-6 h-6" },
};

export function BankLogo({ code, name, size = "md", className = "" }) {
  const [failed, setFailed] = useState(false);
  const s = SIZES[size] || SIZES.md;
  const hasIcon = code && ICONS.has(code) && !failed;

  if (hasIcon) {
    return (
      <span className={`${s.box} ${s.pad} rounded-full bg-white ring-1 ring-white/10 shadow-sm flex items-center justify-center shrink-0 overflow-hidden ${className}`}>
        <img src={`/banks/${code.toLowerCase()}.png`} alt={`${name || code} logo`} loading="lazy" draggable="false"
          onError={() => setFailed(true)} className="w-full h-full object-contain" />
      </span>
    );
  }
  return (
    <span role="img" aria-label={name ? `${name}` : "Bank"}
      className={`${s.box} rounded-full bg-white/[0.08] ring-1 ring-white/10 flex items-center justify-center shrink-0 ${className}`}>
      <Landmark className={`${s.glyph} text-gray-400`} />
    </span>
  );
}
