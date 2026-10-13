import { AlertTriangle, BadgeCheck, Clock, PencilLine, ShieldOff } from "lucide-react";
import { Pill } from "../ui";
import { fmtDateTime, timeAgo } from "../../utils/format";

/** Provenance badge — every figure on screen says where it came from. */
export function CardVerificationStatus({ card, compact = false }) {
  const { card_source: src, verification_status: vs, is_stale: stale } = card;
  let cfg;
  if (src === "USER_ENTERED") {
    cfg = { icon: PencilLine, text: "User-entered — Not Bank Verified", cls: "bg-amber-500/10 text-amber-200 border-amber-500/25" };
  } else if (src === "SAMPLE") {
    cfg = { icon: AlertTriangle, text: "Sample data — development only", cls: "bg-fuchsia-500/10 text-fuchsia-200 border-fuchsia-500/25" };
  } else if (vs === "VERIFIED" && !stale) {
    cfg = { icon: BadgeCheck, text: "Provider-verified", cls: "bg-emerald-500/10 text-emerald-200 border-emerald-500/25" };
  } else if (vs === "VERIFIED" && stale) {
    cfg = { icon: Clock, text: "Verified · data may be out of date", cls: "bg-sky-500/10 text-sky-200 border-sky-500/25" };
  } else {
    cfg = { icon: ShieldOff, text: vs === "CONSENT_EXPIRED" ? "Consent expired — last verified figures" : "Consent revoked — last verified figures",
            cls: "bg-red-500/10 text-red-200 border-red-500/25" };
  }
  const Icon = cfg.icon;
  return (
    <div className={compact ? "" : "space-y-1"}>
      <Pill className={cfg.cls}><Icon className="w-3 h-3" />{cfg.text}</Pill>
      {!compact && (
        <p className="text-[11px] text-gray-500" title={fmtDateTime(card.data_as_of)}>
          {src === "USER_ENTERED" ? "Entered" : "Data as of"} {timeAgo(card.data_as_of)}
        </p>
      )}
    </div>
  );
}
