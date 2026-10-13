import { useEffect, useState } from "react";
import { Eye, SlidersHorizontal } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Button, Field, Skeleton, inputCls, useToast } from "../../components/ui";
import { fmtDateTime } from "../../utils/format";

/** Admin -> Platform settings (admin_settings table). */
export function AdminPlatform() {
  const { api } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [values, setValues] = useState({});
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const apply = (settings) => {
    setRows(settings);
    setValues(Object.fromEntries(settings.map((s) => [s.key, s.raw_value])));
  };
  useEffect(() => { api("/admin/platform-settings").then((r) => (r.ok ? apply(r.data.settings) : toast("error", r.message))); }, [api, toast]);

  const dirty = rows ? Object.fromEntries(rows.filter((s) => (values[s.key] ?? "") !== s.raw_value).map((s) => [s.key, values[s.key]])) : {};
  const save = async (e) => {
    e.preventDefault();
    if (!Object.keys(dirty).length) return;
    setBusy(true);
    const r = await api("/admin/platform-settings", { method: "PATCH", body: { values: dirty } });
    setBusy(false);
    if (r.ok) { apply(r.data.settings); setErrors({}); toast("success", "Settings saved."); }
    else { setErrors(r.errors || {}); toast("error", r.message); }
  };

  return (
    <div className="p-4 lg:p-8 max-w-3xl mx-auto space-y-5">
      <h1 className="text-xl font-bold text-white flex items-center gap-2"><SlidersHorizontal className="w-5 h-5 text-amber-300" /> Platform settings</h1>
      {!rows ? <Skeleton className="h-64" /> : (
        <form onSubmit={save} className="bg-[#0C1220] border border-white/5 rounded-2xl p-5 space-y-5" noValidate>
          {rows.map((s) => (
            <div key={s.key}>
              <Field label={<span className="flex items-center gap-2">{s.label}{s.is_public && <span title="Visible to all app users" className="inline-flex items-center gap-1 text-[10px] text-cyan-300"><Eye className="w-3 h-3" /> public</span>}</span>}
                hint={s.value_type === "DECIMAL" ? "INR" : s.value_type === "INT" ? "number" : ""} error={errors[s.key]}>
                {s.key === "MAINTENANCE_MESSAGE" ? (
                  <textarea rows={2} className={`${inputCls(errors[s.key])} resize-none`} maxLength={500} value={values[s.key] ?? ""}
                    onChange={(e) => setValues({ ...values, [s.key]: e.target.value })} placeholder="Empty = no banner" />
                ) : (
                  <input className={inputCls(errors[s.key])} inputMode={s.value_type === "STRING" ? "text" : "decimal"} maxLength={500}
                    value={values[s.key] ?? ""} onChange={(e) => setValues({ ...values, [s.key]: e.target.value })} />
                )}
              </Field>
              <p className="text-[11px] text-gray-500 mt-1">{s.description} <span className="text-gray-600">· updated {fmtDateTime(s.updated_at)}</span></p>
            </div>
          ))}
          <Button type="submit" className="w-full" loading={busy} disabled={!Object.keys(dirty).length}>
            Save {Object.keys(dirty).length ? `${Object.keys(dirty).length} change(s)` : ""}
          </Button>
        </form>
      )}
    </div>
  );
}
