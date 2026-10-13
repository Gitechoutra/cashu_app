import { useCallback, useEffect, useState } from "react";
import { AlertOctagon, CheckCircle2, GitCompareArrows, RefreshCw } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Banner, Button, Pill, Skeleton, useToast } from "../../components/ui";
import { fmtDateTime } from "../../utils/format";
import { Pager, tableWrap, td, th } from "./AdminLayout";

const RESULT = {
  MATCHED: "bg-white/5 text-gray-300 border-white/10",
  UPDATED: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  MISMATCH: "bg-red-500/10 text-red-300 border-red-500/20",
  ERROR: "bg-amber-500/10 text-amber-300 border-amber-500/20",
};

/** Payment reconciliation history + payment exceptions (reconciliation, transaction_errors). */
export function AdminReconciliation() {
  const { api } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState("errors");
  const [recon, setRecon] = useState(null);
  const [errors, setErrors] = useState(null);
  const [page, setPage] = useState(1);
  const [showResolved, setShowResolved] = useState(false);
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    if (tab === "recon") {
      const r = await api(`/admin/reconciliation?page=${page}&per_page=25`);
      if (r.ok) setRecon(r.data); else toast("error", r.message);
    } else {
      const r = await api(`/admin/transaction-errors?page=${page}&per_page=25&resolved=${showResolved}`);
      if (r.ok) setErrors(r.data); else toast("error", r.message);
    }
  }, [api, tab, page, showResolved, toast]);
  useEffect(() => { load(); }, [load]);

  const run = async () => {
    setRunning(true);
    const r = await api("/admin/reconcile", { method: "POST" });
    setRunning(false);
    if (r.ok) { toast("success", `Checked ${r.data.checked} payment(s): ${r.data.updated} updated, ${r.data.errors} error(s).`); load(); }
    else toast("error", r.message);
  };
  const resolve = async (id) => {
    const r = await api(`/admin/transaction-errors/${id}/resolve`, { method: "POST" });
    if (r.ok) load(); else toast("error", r.message);
  };

  return (
    <div className="p-4 lg:p-8 max-w-6xl mx-auto space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-white flex items-center gap-2"><GitCompareArrows className="w-5 h-5 text-amber-300" /> Reconciliation</h1>
        <Button onClick={run} loading={running}><RefreshCw className="w-4 h-4" /> Run reconciliation</Button>
      </div>
      <Banner>Checks every open payment from the last 48 hours against Razorpay. Statuses only change from data Razorpay returns.</Banner>
      <div className="flex gap-2">
        {[["errors", `Exceptions${errors?.unresolved ? ` · ${errors.unresolved}` : ""}`], ["recon", "History"]].map(([k, l]) => (
          <button key={k} onClick={() => { setTab(k); setPage(1); }}
            className={`text-xs px-3 py-1.5 rounded-full border ${tab === k ? "border-amber-500/40 bg-amber-500/10 text-amber-100" : "border-white/10 text-gray-400"}`}>{l}</button>
        ))}
      </div>

      {tab === "errors" && (
        <>
          <label className="flex items-center gap-2 text-xs text-gray-400"><input type="checkbox" className="accent-amber-500" checked={showResolved}
            onChange={(e) => { setShowResolved(e.target.checked); setPage(1); }} /> Show resolved</label>
          {!errors ? <Skeleton className="h-48" /> : (
            <div className={tableWrap}>
              <table className="w-full">
                <thead><tr className="border-b border-white/5">{["Time", "Stage", "Code", "Message", "Payment", ""].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
                <tbody>
                  {errors.items.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-500"><CheckCircle2 className="w-5 h-5 inline mr-1 text-emerald-400" /> No {showResolved ? "resolved" : "open"} exceptions.</td></tr>}
                  {errors.items.map((e) => (
                    <tr key={e.error_id} className="border-b border-white/5 last:border-0 align-top">
                      <td className={`${td} text-xs`}>{fmtDateTime(e.created_at)}</td>
                      <td className={`${td} text-xs`}>{e.stage}</td>
                      <td className={td}><span className="font-mono text-xs text-red-300 inline-flex items-center gap-1"><AlertOctagon className="w-3.5 h-3.5" /> {e.error_code}</span></td>
                      <td className={`${td} text-xs whitespace-normal max-w-sm`}>{e.message}</td>
                      <td className={`${td} text-xs font-mono`}>{e.receipt_number || "—"}{e.payment_status && <div className="text-gray-500">{e.payment_status}</div>}</td>
                      <td className={`${td} text-right`}>{!e.is_resolved ? <Button size="sm" variant="ghost" onClick={() => resolve(e.error_id)}>Mark resolved</Button> : <span className="text-xs text-gray-500">Resolved {fmtDateTime(e.resolved_at)}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-4 pb-3"><Pager page={errors.page} pages={errors.pages} onPage={setPage} /></div>
            </div>
          )}
        </>
      )}

      {tab === "recon" && (!recon ? <Skeleton className="h-48" /> : (
        <>
          <p className="text-xs text-gray-500">{recon.open_payments} open payment(s) in the last 48 hours.</p>
          <div className={tableWrap}>
            <table className="w-full">
              <thead><tr className="border-b border-white/5">{["Time", "Receipt", "Source", "Before → after", "Gateway", "Result"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
              <tbody>
                {recon.items.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-500">No checks recorded yet.</td></tr>}
                {recon.items.map((r) => (
                  <tr key={r.recon_id} className="border-b border-white/5 last:border-0">
                    <td className={`${td} text-xs`}>{fmtDateTime(r.created_at)}</td>
                    <td className={`${td} text-xs font-mono`}>{r.receipt_number}</td>
                    <td className={`${td} text-xs`}>{r.source}</td>
                    <td className={`${td} text-xs`}>{r.status_before} → {r.status_after}</td>
                    <td className={`${td} text-xs`}>{r.gateway_status || "—"}</td>
                    <td className={td}><Pill className={RESULT[r.result]}>{r.result}</Pill>{r.note && <div className="text-[10px] text-gray-500 mt-1 max-w-[220px] whitespace-normal">{r.note}</div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 pb-3"><Pager page={recon.page} pages={recon.pages} onPage={setPage} /></div>
          </div>
        </>
      ))}
    </div>
  );
}
