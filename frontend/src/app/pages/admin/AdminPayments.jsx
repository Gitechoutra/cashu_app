import { useCallback, useEffect, useState } from "react";
import { ReceiptText, Search } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Pill, Skeleton, inputCls, useToast } from "../../components/ui";
import { PAYMENT_STATUS, SETTLEMENT_LABEL, fmtDateTime, fmtINR } from "../../utils/format";
import { Pager, tableWrap, td, th } from "./AdminLayout";

export function AdminPayments() {
  const { api } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);

  const load = useCallback(async (p = page) => {
    const params = new URLSearchParams({ page: String(p), per_page: "25", ...(status ? { status } : {}), ...(q.trim() ? { q: q.trim() } : {}) });
    const r = await api(`/admin/payments?${params}`);
    if (r.ok) setData(r.data); else toast("error", r.message);
  }, [api, status, q, page, toast]);
  useEffect(() => { load(page); }, [page, status]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="p-4 lg:p-8 max-w-6xl mx-auto space-y-5">
      <h1 className="text-xl font-bold text-white flex items-center gap-2"><ReceiptText className="w-5 h-5 text-amber-300" /> Payments</h1>
      <div className="flex flex-col sm:flex-row gap-2">
        <form className="relative flex-1" onSubmit={(e) => { e.preventDefault(); setPage(1); load(1); }}>
          <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input className={`${inputCls()} pl-10`} placeholder="Exact receipt no. / order_… / pay_…" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        <select className={`${inputCls()} sm:w-48`} value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
          <option value="">All statuses</option>{Object.entries(PAYMENT_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      {!data ? <Skeleton className="h-64" /> : (
        <>
        {/* Phones: one card per payment */}
        <ul className="md:hidden space-y-3">
          {data.items.length === 0 && <li className="text-center text-sm text-gray-500 py-10">No payments found.</li>}
          {data.items.map((p) => {
            const s = PAYMENT_STATUS[p.status] || PAYMENT_STATUS.CREATED;
            return (
              <li key={p.payment_id} className="bg-[#0C1220] border border-white/5 rounded-2xl p-4 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-lg font-bold text-white">{fmtINR(p.amount)} <span className="text-[10px] text-gray-500 uppercase font-normal">{p.provider_mode}</span></div>
                    <div className="text-xs text-gray-500">{fmtDateTime(p.created_at)}</div>
                  </div>
                  <Pill className={s.cls}>{s.label}</Pill>
                </div>
                <div className="text-sm text-gray-300">{p.customer.full_name || "—"} <span className="text-gray-500 text-xs">{p.customer.mobile_number}</span></div>
                <div className="text-xs text-gray-400">{p.card_nickname} {p.masked_number}{p.verified_via ? ` · via ${p.verified_via}` : ""}</div>
                {p.status === "SUCCESS" && <div className="text-[11px] text-gray-500">{SETTLEMENT_LABEL[p.settlement_status]}</div>}
                <div className="font-mono text-[10px] text-gray-500 break-all">{p.receipt_number} · {p.provider_order_id}</div>
              </li>
            );
          })}
          <Pager page={data.page} pages={data.pages} onPage={setPage} />
        </ul>
        <div className={`hidden md:block ${tableWrap}`}>
          <table className="w-full">
            <thead><tr className="border-b border-white/5">{["Created", "Customer", "Card", "Amount", "Status", "Issuer credit", "Receipt / refs"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
            <tbody>
              {data.items.length === 0 && <tr><td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-500">No payments found.</td></tr>}
              {data.items.map((p) => {
                const s = PAYMENT_STATUS[p.status] || PAYMENT_STATUS.CREATED;
                return (
                  <tr key={p.payment_id} className="border-b border-white/5 last:border-0">
                    <td className={td}>{fmtDateTime(p.created_at)}</td>
                    <td className={td}><div className="text-white">{p.customer.full_name || "—"}</div><div className="text-[11px] text-gray-500">{p.customer.mobile_number}</div></td>
                    <td className={td}>{p.card_nickname} <span className="text-gray-500">{p.masked_number}</span></td>
                    <td className={`${td} text-white font-semibold`}>{fmtINR(p.amount)}<div className="text-[10px] text-gray-500 font-normal uppercase">{p.provider_mode}</div></td>
                    <td className={td}><Pill className={s.cls}>{s.label}</Pill>{p.verified_via && <div className="text-[10px] text-gray-500 mt-1">via {p.verified_via}</div>}</td>
                    <td className={`${td} text-xs`}><div className="w-52 whitespace-normal leading-snug text-gray-400">{p.status === "SUCCESS" ? SETTLEMENT_LABEL[p.settlement_status] : "—"}</div></td>
                    <td className={`${td} font-mono text-[11px]`}><div>{p.receipt_number}</div><div className="text-gray-500">{p.provider_order_id}</div>{p.provider_payment_id && <div className="text-gray-500">{p.provider_payment_id}</div>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="px-4 pb-3"><Pager page={data.page} pages={data.pages} onPage={setPage} /></div>
        </div>
        </>
      )}
    </div>
  );
}
