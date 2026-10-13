import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Bell, CalendarClock, CheckCheck, Headset, IndianRupee, ShieldAlert } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Button, EmptyState, Skeleton, useToast } from "../../components/ui";
import { timeAgo } from "../../utils/format";

const ICONS = {
  PAYMENT: [IndianRupee, "text-emerald-300 bg-emerald-500/10"],
  BILL_DUE: [CalendarClock, "text-amber-300 bg-amber-500/10"],
  SUPPORT: [Headset, "text-violet-300 bg-violet-500/10"],
  SECURITY: [ShieldAlert, "text-red-300 bg-red-500/10"],
  SYSTEM: [Bell, "text-cyan-300 bg-cyan-500/10"],
};

export function Notifications() {
  const { api } = useAuth();
  const toast = useToast();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [onlyUnread, setOnlyUnread] = useState(false);

  const load = useCallback(async () => {
    const r = await api(`/notifications?per_page=50${onlyUnread ? "&unread=true" : ""}`);
    if (r.ok) setData(r.data); else toast("error", r.message);
  }, [api, onlyUnread, toast]);
  useEffect(() => { load(); }, [load]);

  const markAll = async () => {
    const r = await api("/notifications/read", { method: "POST", body: { all: true } });
    if (r.ok) load();
  };
  const open = async (n) => {
    if (!n.is_read) await api("/notifications/read", { method: "POST", body: { ids: [n.notification_id] } });
    if (n.link?.startsWith("/")) nav(n.link); else load();
  };

  return (
    <div className="p-4 lg:p-8 max-w-2xl mx-auto space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-white flex items-center gap-2"><Bell className="w-5 h-5 text-cyan-300" /> Notifications</h1>
        <Button size="sm" variant="ghost" onClick={markAll} disabled={!data?.unread}><CheckCheck className="w-3.5 h-3.5" /> Mark all read</Button>
      </div>
      <div className="flex gap-2">
        {[[false, "All"], [true, `Unread${data?.unread ? ` · ${data.unread}` : ""}`]].map(([v, l]) => (
          <button key={String(v)} onClick={() => setOnlyUnread(v)}
            className={`text-xs px-3 py-1.5 rounded-full border ${onlyUnread === v ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-200" : "border-white/10 text-gray-400"}`}>{l}</button>
        ))}
      </div>
      {!data ? <Skeleton className="h-48" /> : data.items.length === 0 ? (
        <EmptyState icon={Bell} title="You're all caught up" text="Payment updates, due-date reminders and support replies show up here." />
      ) : (
        <ul className="bg-[#0C1220] border border-white/5 rounded-2xl divide-y divide-white/5 overflow-hidden">
          {data.items.map((n) => {
            const [Icon, tone] = ICONS[n.type] || ICONS.SYSTEM;
            return (
              <li key={n.notification_id}>
                <button onClick={() => open(n)} className={`w-full text-left flex items-start gap-3 px-4 py-3.5 hover:bg-white/[0.03] ${n.is_read ? "" : "bg-cyan-500/[0.03]"}`}>
                  <span className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${tone}`}><Icon className="w-4 h-4" /></span>
                  <span className="flex-1 min-w-0">
                    <span className={`block text-sm ${n.is_read ? "text-gray-300" : "text-white font-medium"}`}>{n.title}</span>
                    {n.body && <span className="block text-xs text-gray-500 mt-0.5">{n.body}</span>}
                    <span className="block text-[11px] text-gray-600 mt-1">{timeAgo(n.created_at)}</span>
                  </span>
                  {!n.is_read && <span className="w-2 h-2 rounded-full bg-cyan-400 mt-2 shrink-0" aria-label="Unread" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
