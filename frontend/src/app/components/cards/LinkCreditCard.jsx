import { useState } from "react";
import { ExternalLink, Landmark, Lock, PlugZap, ShieldCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Button, useToast } from "../ui";

/** Authorised bank-linking: explains exactly what is shared, records consent,
 *  then hands the user to the PROVIDER's own consent screen. This app never
 *  renders a bank login page or asks for bank credentials / OTPs. */
export function LinkCreditCard({ issuer, linkConfig, onBack, onManual }) {
  const { api } = useAuth();
  const toast = useToast();
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!linkConfig?.configured) {
    return (
      <div className="space-y-4">
        <div className="flex flex-col items-center text-center py-4">
          <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-3">
            <PlugZap className="w-5 h-5 text-gray-400" />
          </div>
          <h4 className="text-sm font-semibold text-white">Bank integration not configured</h4>
          <p className="text-sm text-gray-500 mt-1 max-w-sm">
            Secure linking needs an authorised financial-data provider (such as an RBI-licensed Account Aggregator),
            which hasn't been set up for this app yet. You can add the card manually now.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" className="flex-1" onClick={onBack}>Back</Button>
          <Button className="flex-1" onClick={onManual}>Add manually</Button>
        </div>
      </div>
    );
  }

  if (!issuer.linkable) {
    return (
      <div className="space-y-4">
        <Banner tone="warn" icon={Landmark}>
          {issuer.name} doesn't share credit card data through {linkConfig.provider} yet. Banks differ in what they
          provide, so we can't assume it works the same way. Add the card manually instead.
        </Banner>
        <div className="flex gap-2">
          <Button variant="ghost" className="flex-1" onClick={onBack}>Back</Button>
          <Button className="flex-1" onClick={onManual}>Add manually</Button>
        </div>
      </div>
    );
  }

  const start = async () => {
    if (busy) return;
    setBusy(true);
    const r = await api("/cards/link-session", { method: "POST", body: { issuer_id: issuer.issuer_id, consent_acknowledged: true } });
    if (r.ok && r.data.redirect_url?.startsWith("https://")) {
      window.location.assign(r.data.redirect_url);   // provider-hosted consent page
      return;
    }
    setBusy(false);
    toast("error", r.ok ? "The provider returned an invalid link." : r.message);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-[#141C30]/60 p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm text-white font-medium"><ShieldCheck className="w-4 h-4 text-cyan-300" /> What will be shared</div>
        <p className="text-xs text-gray-400">Purpose: {linkConfig.purpose}.</p>
        <ul className="grid grid-cols-2 gap-1.5 text-xs text-gray-300">
          {(linkConfig.data_accessed || []).map((d) => <li key={d} className="capitalize">• {d}</li>)}
        </ul>
        <p className="text-[11px] text-gray-500">
          You'll approve this on {linkConfig.provider}'s secure page. You can revoke consent any time in Settings → Data &amp; consents,
          and removing a card deletes its stored data.
        </p>
      </div>
      <Banner tone="info" icon={Lock}>
        You'll be taken to the provider to sign in and approve. CardVault never sees your bank password or OTP.
      </Banner>
      <label className="flex items-start gap-2.5 text-sm text-gray-300 cursor-pointer">
        <input type="checkbox" className="mt-0.5 accent-cyan-500 w-4 h-4" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        I consent to {linkConfig.provider} sharing the data listed above from {issuer.name} with CardVault.
      </label>
      <div className="flex gap-2">
        <Button variant="ghost" className="flex-1" onClick={onBack} disabled={busy}>Back</Button>
        <Button className="flex-1" disabled={!agreed} loading={busy} onClick={start}>
          Continue to {linkConfig.provider} <ExternalLink className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}
