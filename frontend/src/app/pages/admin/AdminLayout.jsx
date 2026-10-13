import { Building2, GitCompareArrows, Inbox, KeyRound, LayoutDashboard, ReceiptText, ScrollText, Settings, SlidersHorizontal, Users } from "lucide-react";
import { AppShell } from "../../components/AppShell";

export const ADMIN_NAV = [
  { to: "/admin", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/payments", label: "Payments", icon: ReceiptText },
  { to: "/admin/tickets", label: "Tickets", icon: Inbox },
  { to: "/admin/gateways", label: "Gateways", icon: KeyRound },
  { to: "/admin/reconciliation", label: "Reconciliation", icon: GitCompareArrows, mobile: false },
  { to: "/admin/platform", label: "Platform settings", icon: SlidersHorizontal, mobile: false },
  { to: "/admin/banks", label: "Banks", icon: Building2, mobile: false },
  { to: "/admin/audit", label: "Audit log", icon: ScrollText, mobile: false },
  { to: "/admin/settings", label: "Settings", icon: Settings, mobile: false },
];

/** Admin (ADMIN role) area. */
export function AdminLayout() {
  return <AppShell role="ADMIN" nav={ADMIN_NAV} accent="amber" settingsPath="/admin/settings" />;
}

/** Simple pager for the admin tables. */
export function Pager({ page, pages, onPage }) {
  if (!pages || pages <= 1) return null;
  return (
    <div className="flex items-center justify-end gap-2 text-xs text-gray-400 pt-3">
      <button disabled={page <= 1} onClick={() => onPage(page - 1)} className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 disabled:opacity-40">Prev</button>
      <span>Page {page} of {pages}</span>
      <button disabled={page >= pages} onClick={() => onPage(page + 1)} className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 disabled:opacity-40">Next</button>
    </div>
  );
}

export const tableWrap = "bg-[#0C1220] border border-white/5 rounded-2xl overflow-x-auto";
export const th = "px-4 py-3 text-left text-[11px] uppercase tracking-wider text-gray-500 font-medium whitespace-nowrap";
export const td = "px-4 py-3 text-sm text-gray-300 whitespace-nowrap";
