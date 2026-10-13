import { useCallback, useEffect, useState } from "react";
import { Building2, Search, Star } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { BankLogo } from "../../components/BankLogo";
import { Skeleton, inputCls, useToast } from "../../components/ui";

/** Issuing banks shown in the Add Card picker: enable/disable and mark Popular. */
export function AdminBanks() {
  const { api } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    const r = await api("/admin/issuers");
    if (r.ok) setRows(r.data.issuers); else toast("error", r.message);
  }, [api, toast]);
  useEffect(() => { load(); }, [load]);

  const patch = async (i, body) => {
    setBusy(i.issuer_id);
    const r = await api(`/admin/issuers/${i.issuer_id}`, { method: "PATCH", body });
    setBusy(null);
    if (r.ok) load(); else toast("error", r.message);
  };

  const shown = (rows || []).filter((i) => i.name.toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-5">
      <h1 className="text-xl font-bold text-white flex items-center gap-2"><Building2 className="w-5 h-5 text-amber-300" /> Banks</h1>
      <div className="relative">
        <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <input className={`${inputCls()} pl-10`} placeholder="Search banks" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {!rows ? <Skeleton className="h-64" /> : (
        <ul className="bg-[#0C1220] border border-white/5 rounded-2xl divide-y divide-white/5">
          {shown.map((i) => (
            <li key={i.issuer_id} className={`flex items-center gap-3 px-4 py-3 ${i.is_active ? "" : "opacity-50"}`}>
              <BankLogo code={i.code} name={i.name} size="md" />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-white truncate">{i.name}</div>
                <div className="text-[11px] text-gray-500">{i.code} · {i.cards} active card{i.cards === 1 ? "" : "s"}</div>
              </div>
              {i.code !== "OTHER" && (
                <button disabled={busy === i.issuer_id} onClick={() => patch(i, { popular: !i.popular })} aria-label="Toggle popular"
                  title={i.popular ? "Shown in Popular grid" : "Add to Popular grid"}
                  className={`p-2 rounded-lg ${i.popular ? "text-amber-300" : "text-gray-600 hover:text-gray-300"}`}>
                  <Star className={`w-4 h-4 ${i.popular ? "fill-current" : ""}`} />
                </button>
              )}
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input type="checkbox" className="accent-amber-500 w-4 h-4" disabled={busy === i.issuer_id} checked={i.is_active}
                  onChange={(e) => patch(i, { is_active: e.target.checked })} />
                <span className="hidden sm:inline">{i.is_active ? "Enabled" : "Disabled"}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <p className="text-[11px] text-gray-600">Disabled banks are hidden from the Add Card picker. Existing cards are not affected.</p>
    </div>
  );
}
