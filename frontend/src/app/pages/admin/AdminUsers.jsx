import { useCallback, useEffect, useState } from "react";
import { AnimatePresence } from "motion/react";
import { Search, UserPlus, Users } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Button, ConfirmDialog, Field, ModalShell, Pill, Skeleton, inputCls, useToast } from "../../components/ui";
import { validateMobile, validatePin } from "../../utils/validation";
import { fmtDateTime } from "../../utils/format";
import { Pager, tableWrap, td, th } from "./AdminLayout";

const ROLE_PILL = {
  ADMIN: "bg-amber-500/10 text-amber-200 border-amber-500/25",
  SUPPORT: "bg-violet-500/10 text-violet-200 border-violet-500/25",
  USER: "bg-white/5 text-gray-300 border-white/10",
};

export function AdminUsers() {
  const { api, user: me } = useAuth();
  const toast = useToast();
  const [filters, setFilters] = useState({ q: "", role: "", status: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [confirm, setConfirm] = useState(null);     // { user, patch, label }
  const [busy, setBusy] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [resetting, setResetting] = useState(null);

  const load = useCallback(async (p = page) => {
    const params = new URLSearchParams({ page: String(p), per_page: "20" });
    Object.entries(filters).forEach(([k, v]) => v && params.set(k, v));
    const r = await api(`/admin/users?${params}`);
    if (r.ok) setData(r.data); else toast("error", r.message);
  }, [api, filters, page, toast]);
  useEffect(() => { load(page); }, [page, filters.role, filters.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const apply = async () => {
    setBusy(true);
    const r = await api(`/admin/users/${confirm.user.user_id}`, { method: "PATCH", body: confirm.patch });
    setBusy(false);
    if (r.ok) { toast("success", "User updated — their sessions were signed out."); setConfirm(null); load(); }
    else toast("error", r.message);
  };

  return (
    <div className="p-4 lg:p-8 max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-white flex items-center gap-2"><Users className="w-5 h-5 text-amber-300" /> Users & roles</h1>
        <Button onClick={() => setInviting(true)}><UserPlus className="w-4 h-4" /> <span className="hidden sm:inline">Add staff</span></Button>
      </div>
      <div className="flex flex-col sm:flex-row gap-2">
        <form className="relative flex-1" onSubmit={(e) => { e.preventDefault(); setPage(1); load(1); }}>
          <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input className={`${inputCls()} pl-10`} placeholder="Search name or mobile digits" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
        </form>
        <select className={`${inputCls()} sm:w-44`} value={filters.role} onChange={(e) => { setPage(1); setFilters({ ...filters, role: e.target.value }); }}>
          <option value="">All roles</option><option value="ADMIN">Admin</option><option value="SUPPORT">Customer Support</option><option value="USER">User</option>
        </select>
        <select className={`${inputCls()} sm:w-40`} value={filters.status} onChange={(e) => { setPage(1); setFilters({ ...filters, status: e.target.value }); }}>
          <option value="">All statuses</option><option value="ACTIVE">Active</option><option value="SUSPENDED">Suspended</option>
        </select>
      </div>

      {!data ? <Skeleton className="h-64" /> : (
        <>
        {/* Phones: one card per user */}
        <ul className="md:hidden space-y-3">
          {data.items.length === 0 && <li className="text-center text-sm text-gray-500 py-10">No users found.</li>}
          {data.items.map((u) => {
            const self = u.user_id === me?.user_id;
            return (
              <li key={u.user_id} className="bg-[#0C1220] border border-white/5 rounded-2xl p-4 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-white truncate">{u.full_name || "—"}{self && <span className="text-gray-500"> (you)</span>}</div>
                    <div className="text-[11px] text-gray-500 truncate">{u.email || u.mobile_number}</div>
                  </div>
                  <Pill className={ROLE_PILL[u.role]}>{u.role === "SUPPORT" ? "Support" : u.role === "ADMIN" ? "Admin" : "User"}</Pill>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
                  <Pill className={u.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-red-500/10 text-red-300 border-red-500/20"}>{u.status}</Pill>
                  {u.role === "USER" && <span>KYC {(u.kyc_status || "NOT_STARTED").replace("_", " ")} · {u.cards} card(s)</span>}
                  <span>Last login {fmtDateTime(u.last_login)}</span>
                </div>
                {u.seed_managed ? <div className="text-[11px] text-gray-500">Managed in seed file</div> : !self && (
                  <div className="flex gap-4 pt-1">
                    {u.role !== "USER" && (
                      <select value={u.role} className={`text-xs rounded-lg px-2 py-1.5 border bg-transparent ${ROLE_PILL[u.role]}`}
                        onChange={(e) => setConfirm({ user: u, patch: { role: e.target.value }, label: `Change ${u.full_name || u.email}'s role?` })}>
                        <option value="ADMIN" className="bg-[#141C30]">Admin</option>
                        <option value="SUPPORT" className="bg-[#141C30]">Customer Support</option>
                      </select>
                    )}
                    {u.role !== "USER" && <button onClick={() => setResetting(u)} className="text-xs text-amber-300">Reset PIN</button>}
                    <button onClick={() => setConfirm({ user: u, patch: { status: u.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE" },
                      label: `${u.status === "ACTIVE" ? "Suspend" : "Reactivate"} ${u.full_name || u.mobile_number}?` })}
                      className={`text-xs ${u.status === "ACTIVE" ? "text-red-300" : "text-emerald-300"}`}>{u.status === "ACTIVE" ? "Suspend" : "Reactivate"}</button>
                  </div>
                )}
              </li>
            );
          })}
          <Pager page={data.page} pages={data.pages} onPage={setPage} />
        </ul>
        <div className={`hidden md:block ${tableWrap}`}>
          <table className="w-full">
            <thead><tr className="border-b border-white/5">{["User", "Role", "Status", "KYC", "Cards", "Last login", ""].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
            <tbody>
              {data.items.length === 0 && <tr><td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-500">No users found.</td></tr>}
              {data.items.map((u) => {
                const self = u.user_id === me?.user_id;
                return (
                  <tr key={u.user_id} className="border-b border-white/5 last:border-0">
                    <td className={td}><div className="text-white">{u.full_name || "—"}{self && <span className="text-gray-500"> (you)</span>}</div><div className="text-[11px] text-gray-500">{u.mobile_number}</div></td>
                    <td className={td}>
                      {u.role === "USER" ? <Pill className={ROLE_PILL.USER}>User</Pill> : (
                        <select value={u.role} disabled={self || u.seed_managed} title={u.seed_managed ? "Managed in the seed file" : undefined}
                          onChange={(e) => setConfirm({ user: u, patch: { role: e.target.value }, label: `Change ${u.full_name || u.email}'s role to ${e.target.value === "ADMIN" ? "Admin" : "Customer Support"}?` })}
                          className={`text-xs rounded-lg px-2 py-1.5 border bg-transparent ${ROLE_PILL[u.role]} disabled:opacity-60`}>
                          <option value="ADMIN" className="bg-[#141C30]">Admin</option>
                          <option value="SUPPORT" className="bg-[#141C30]">Customer Support</option>
                        </select>
                      )}
                      {u.email && <div className="text-[10px] text-gray-500 mt-1">{u.email}</div>}
                      {u.pin_reset_required && <div className="text-[10px] text-amber-300 mt-0.5">Temporary PIN - not yet changed</div>}
                    </td>
                    <td className={td}><Pill className={u.status === "ACTIVE" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-red-500/10 text-red-300 border-red-500/20"}>{u.status}</Pill></td>
                    <td className={`${td} text-xs`}>{u.role === "USER" ? (u.kyc_status || "NOT_STARTED").replace("_", " ") : "—"}</td>
                    <td className={td}>{u.cards}</td>
                    <td className={td}>{fmtDateTime(u.last_login)}</td>
                    <td className={`${td} text-right`}>
                      {u.seed_managed && <span className="text-[11px] text-gray-500">Managed in seed file</span>}
                      {!self && !u.seed_managed && u.role !== "USER" && (
                        <button onClick={() => setResetting(u)} className="text-xs text-amber-300 hover:text-amber-200 mr-3">Reset PIN</button>
                      )}
                      {!self && !u.seed_managed && (
                        <button onClick={() => setConfirm({ user: u, patch: { status: u.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE" },
                          label: `${u.status === "ACTIVE" ? "Suspend" : "Reactivate"} ${u.full_name || u.mobile_number}?` })}
                          className={`text-xs ${u.status === "ACTIVE" ? "text-red-300 hover:text-red-200" : "text-emerald-300 hover:text-emerald-200"}`}>
                          {u.status === "ACTIVE" ? "Suspend" : "Reactivate"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="px-4 pb-3"><Pager page={data.page} pages={data.pages} onPage={setPage} /></div>
        </div>
        </>
      )}

      <AnimatePresence>
        {confirm && (
          <ConfirmDialog title="Confirm change" busy={busy} danger={confirm.patch.status === "SUSPENDED"} confirmLabel="Confirm"
            message={`${confirm.label} They will be signed out of every device so the change takes effect immediately.`}
            onConfirm={apply} onClose={() => setConfirm(null)} />
        )}
        {inviting && <InviteStaff onClose={() => setInviting(false)} onDone={() => { setInviting(false); load(1); }} />}
        {resetting && <ResetStaffPin user={resetting} onClose={() => setResetting(null)} onDone={() => { setResetting(null); load(); }} />}
      </AnimatePresence>
    </div>
  );
}

const genPin = () => {
  // Random 6-digit PIN that passes the server's "not repeated / sequential" rule.
  for (;;) {
    const p = String(crypto.getRandomValues(new Uint32Array(1))[0] % 1000000).padStart(6, "0");
    if (!validatePin(p)) return p;
  }
};

function TempPinField({ value, onChange, error }) {
  return (
    <Field label="Temporary 6-digit PIN" hint="share it privately" error={error}>
      <div className="flex gap-2">
        <input className={`${inputCls(error)} font-mono tracking-[0.4em] text-center`} inputMode="numeric" maxLength={6} value={value}
          onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))} />
        <Button type="button" variant="ghost" size="sm" onClick={() => onChange(genPin())}>Generate</Button>
      </div>
    </Field>
  );
}

function InviteStaff({ onClose, onDone }) {
  const { api } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ mobile_number: "", email: "", full_name: "", role: "SUPPORT", temporary_pin: genPin() });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    const er = {};
    const m = validateMobile(f.mobile_number); if (m) er.mobile_number = m;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(f.email.trim())) er.email = "Enter a valid email address.";
    if (!/^\d{6}$/.test(f.temporary_pin) || validatePin(f.temporary_pin)) er.temporary_pin = "Use 6 digits, not repeated or sequential.";
    setErrors(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    const r = await api("/admin/users", { method: "POST", body: { ...f, email: f.email.trim().toLowerCase() } });
    setBusy(false);
    if (r.ok) {
      toast("success", `Staff account created. They sign in at /${f.role === "ADMIN" ? "admin" : "support"}/login with ${f.email.trim()} and the temporary PIN.`);
      onDone();
    } else {
      setErrors({ ...(r.errors || {}), _: r.errors && Object.keys(r.errors).length ? "" : r.message });
    }
  };
  return (
    <ModalShell title="Add staff member" subtitle="They sign in with email + PIN (no OTP) and must replace the temporary PIN at first sign-in." onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        <Field label="Role">
          <select className={inputCls()} value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
            <option value="SUPPORT">Customer Support</option><option value="ADMIN">Admin</option>
          </select>
        </Field>
        <Field label="Work email" error={errors.email}>
          <input type="email" className={inputCls(errors.email)} value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="name@company.com" />
        </Field>
        <Field label="Full name" optional><input className={inputCls()} maxLength={100} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Mobile number" hint="separate from any customer account" error={errors.mobile_number}>
          <input className={inputCls(errors.mobile_number)} inputMode="numeric" value={f.mobile_number}
            onChange={(e) => setF({ ...f, mobile_number: e.target.value.replace(/\D/g, "").slice(0, 10) })} placeholder="98765 43210" />
        </Field>
        <TempPinField value={f.temporary_pin} onChange={(v) => setF({ ...f, temporary_pin: v })} error={errors.temporary_pin} />
        {errors._ && <p className="text-sm text-red-300">{errors._}</p>}
        <Button type="submit" className="w-full" loading={busy}>Create staff account</Button>
      </form>
    </ModalShell>
  );
}

function ResetStaffPin({ user, onClose, onDone }) {
  const { api } = useAuth();
  const toast = useToast();
  const [pin, setPin] = useState(genPin());
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await api(`/admin/users/${user.user_id}/reset-pin`, { method: "POST", body: { temporary_pin: pin } });
    setBusy(false);
    if (r.ok) { toast("success", r.data.message); onDone(); } else setErr(r.message);
  };
  return (
    <ModalShell title="Reset staff PIN" subtitle={`${user.full_name || user.email} will be signed out everywhere and must set a new PIN at next sign-in.`} onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="space-y-3" noValidate>
        <TempPinField value={pin} onChange={setPin} error={err} />
        <Button type="submit" className="w-full" loading={busy}>Set temporary PIN</Button>
      </form>
    </ModalShell>
  );
}
