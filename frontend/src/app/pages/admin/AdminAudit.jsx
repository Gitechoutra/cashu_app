import { useCallback, useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Pill, Skeleton, inputCls, useToast } from "../../components/ui";
import { fmtDateTime } from "../../utils/format";
import { Pager, tableWrap, td, th } from "./AdminLayout";

export function AdminAudit() {
  const { api } = useAuth();
  const toast = useToast();
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);

  const load = useCallback(async (p = page) => {
    const params = new URLSearchParams({ page: String(p), per_page: "30", ...(action.trim() ? { action: action.trim() } : {}) });
    const r = await api(`/admin/audit-logs?${params}`);
    if (r.ok) setData(r.data); else toast("error", r.message);
  }, [api, action, page, toast]);
  useEffect(() => { load(page); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-4 lg:p-8 max-w-6xl mx-auto space-y-5">
      <h1 className="text-xl font-bold text-white flex items-center gap-2"><ScrollText className="w-5 h-5 text-amber-300" /> Audit log</h1>
      <form onSubmit={(e) => { e.preventDefault(); setPage(1); load(1); }}>
        <input className={`${inputCls()} sm:max-w-sm font-mono`} placeholder="Filter by action, e.g. CARD_REMOVED" value={action} onChange={(e) => setAction(e.target.value.toUpperCase())} />
      </form>
      {!data ? <Skeleton className="h-64" /> : (
        <div className={tableWrap}>
          <table className="w-full">
            <thead><tr className="border-b border-white/5">{["Time", "Actor", "Action", "Entity", "Details", "IP"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
            <tbody>
              {data.items.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-500">No entries.</td></tr>}
              {data.items.map((a) => (
                <tr key={a.log_id} className="border-b border-white/5 last:border-0 align-top">
                  <td className={`${td} text-xs`}>{fmtDateTime(a.created_on)}</td>
                  <td className={`${td} text-xs`}>{a.actor ? <><div className="text-gray-200">{a.actor.full_name || "—"}</div><div className="text-gray-500">{a.actor.mobile_number} · {a.actor.role}</div></> : "—"}</td>
                  <td className={td}><span className="font-mono text-xs text-white">{a.action}</span>{a.status !== "SUCCESS" && <Pill className="ml-2 bg-red-500/10 text-red-300 border-red-500/20">{a.status}</Pill>}</td>
                  <td className={`${td} text-xs font-mono`}>{a.entity_type ? `${a.entity_type}:${a.entity_id ?? ""}` : "—"}</td>
                  <td className={`${td} text-[11px] font-mono text-gray-400 whitespace-normal max-w-xs break-all`}>{a.details ? JSON.stringify(a.details) : "—"}</td>
                  <td className={`${td} text-xs text-gray-500`}>{a.ip_address || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 pb-3"><Pager page={data.page} pages={data.pages} onPage={setPage} /></div>
        </div>
      )}
    </div>
  );
}
