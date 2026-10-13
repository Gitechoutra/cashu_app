import { useEffect, useState } from "react";
import { Link } from "react-router";
import { CreditCard, Inbox, IndianRupee, TrendingUp, Users } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Skeleton } from "../../components/ui";
import { fmtINR } from "../../utils/format";
import { ADMIN_NAV } from "./AdminLayout";

export function AdminDashboard() {
  const { api, user } = useAuth();
  const [s, setS] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/admin/stats").then((r) => (r.ok ? setS(r.data) : setErr(r.message))); }, [api]);

  const tiles = s ? [
    { label: "Users", value: s.users.total, sub: `${s.users.new_30d} new in 30 days · ${s.users.suspended} suspended`, icon: Users, to: "/admin/users" },
    { label: "Active cards", value: s.cards.active, sub: `${s.cards.verified} bank-verified`, icon: CreditCard, to: "/admin/banks" },
    { label: "Payments (30d)", value: fmtINR(s.payments_30d.volume, { compact: true }),
      sub: `${s.payments_30d.successful}/${s.payments_30d.count} successful${s.payments_30d.success_rate !== null ? ` · ${s.payments_30d.success_rate}%` : ""}`, icon: IndianRupee, to: "/admin/payments" },
    { label: "Open tickets", value: s.tickets.open, sub: `${s.tickets.unassigned} unassigned`, icon: Inbox, to: "/admin/tickets" },
  ] : [];
  const max = Math.max(1, ...(s?.daily_payments || []).map((d) => Number(d.volume)));

  return (
    <div className="p-4 lg:p-8 max-w-6xl mx-auto space-y-6">
      <div>
        <p className="text-sm text-gray-500">Admin console</p>
        <h1 className="text-2xl font-bold text-white">Welcome, {user?.full_name?.split(" ")[0] || "Admin"}</h1>
      </div>
      {err && <Banner tone="error">{err}</Banner>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {!s ? [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />) : tiles.map((t) => (
          <Link key={t.label} to={t.to} className="bg-[#0C1220] border border-white/5 hover:border-amber-500/25 rounded-2xl p-4 transition-colors">
            <div className="flex items-center justify-between mb-2"><span className="text-xs text-gray-500">{t.label}</span><t.icon className="w-4 h-4 text-amber-300" /></div>
            <div className="text-2xl font-bold text-white">{t.value}</div>
            <div className="text-[11px] text-gray-500 mt-1">{t.sub}</div>
          </Link>
        ))}
      </div>

      {s && (
        <div className="grid lg:grid-cols-[1fr_280px] gap-4">
          <section className="bg-[#0C1220] border border-white/5 rounded-2xl p-5">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2 mb-4"><TrendingUp className="w-4 h-4 text-amber-300" /> Successful payments · last 14 days</h2>
            {s.daily_payments.length === 0 ? <p className="text-sm text-gray-500 py-8 text-center">No successful payments yet.</p> : (
              <div className="flex items-end gap-1.5 h-40">
                {s.daily_payments.map((d) => (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1 min-w-0" title={`${d.date}: ${d.count} payments · ${fmtINR(d.volume)}`}>
                    <div className="w-full rounded-t-md bg-gradient-to-t from-amber-500/40 to-amber-300" style={{ height: `${Math.max(4, (Number(d.volume) / max) * 100)}%` }} />
                    <span className="text-[9px] text-gray-600 truncate">{d.date.slice(5)}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
          <section className="bg-[#0C1220] border border-white/5 rounded-2xl p-5">
            <h2 className="text-sm font-semibold text-white mb-3">Users by role</h2>
            {[["ADMIN", "Admin"], ["SUPPORT", "Customer Support"], ["USER", "Users"]].map(([k, l]) => (
              <div key={k} className="flex justify-between py-1.5 text-sm"><span className="text-gray-400">{l}</span><span className="text-white font-semibold">{s.users.by_role[k] || 0}</span></div>
            ))}
          </section>
        </div>
      )}

      <section>
        <h2 className="text-sm font-semibold text-white mb-3">Manage</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {ADMIN_NAV.filter((n) => n.to !== "/admin" && n.to !== "/admin/settings").map((n) => (
            <Link key={n.to} to={n.to} className="flex flex-col items-center gap-2 bg-[#0C1220] border border-white/5 hover:border-amber-500/25 rounded-2xl p-4 text-sm text-gray-300 hover:text-white">
              <n.icon className="w-5 h-5 text-amber-300" /> {n.label}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
