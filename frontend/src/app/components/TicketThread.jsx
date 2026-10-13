import { useEffect, useRef, useState } from "react";
import { Lock, Send } from "lucide-react";
import { Button } from "./ui";
import { fmtDateTime } from "../utils/format";

export const TICKET_STATUS = {
  OPEN: { label: "Open", cls: "bg-sky-500/10 text-sky-300 border-sky-500/20" },
  IN_PROGRESS: { label: "In progress", cls: "bg-violet-500/10 text-violet-300 border-violet-500/20" },
  WAITING_ON_USER: { label: "Awaiting reply", cls: "bg-amber-500/10 text-amber-300 border-amber-500/20" },
  RESOLVED: { label: "Resolved", cls: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" },
  CLOSED: { label: "Closed", cls: "bg-white/5 text-gray-400 border-white/10" },
};

export const PRIORITY = {
  LOW: "text-gray-400", NORMAL: "text-sky-300", HIGH: "text-amber-300", URGENT: "text-red-300",
};

/** Chat-style conversation. `viewer` = "CUSTOMER" | "SUPPORT"; staff can post internal notes. */
export function TicketThread({ messages, viewer, onSend, disabled, disabledReason }) {
  const [text, setText] = useState("");
  const [internal, setInternal] = useState(false);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [messages?.length]);

  const send = async (e) => {
    e.preventDefault();
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    const ok = await onSend(body, internal);
    setBusy(false);
    if (ok) { setText(""); setInternal(false); }
  };

  return (
    <div className="flex flex-col min-h-0">
      <div className="space-y-3 overflow-y-auto pr-1 max-h-[55vh]">
        {messages.map((m) => {
          const mine = m.from === viewer;
          return (
            <div key={m.message_id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                m.is_internal ? "bg-amber-500/10 border border-amber-500/25 text-amber-50"
                : mine ? "bg-cyan-500/15 border border-cyan-500/20 text-gray-100" : "bg-white/[0.05] border border-white/10 text-gray-200"}`}>
                <div className="flex items-center gap-2 text-[11px] text-gray-400 mb-1">
                  {m.is_internal && <Lock className="w-3 h-3 text-amber-300" />}
                  <span>{m.is_internal ? "Internal note · " : ""}{m.sender_name || (m.from === "CUSTOMER" ? "Customer" : "Support")}</span>
                  <span>· {fmtDateTime(m.created_at)}</span>
                </div>
                <div className="whitespace-pre-wrap break-words">{m.body}</div>
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
      {disabled ? (
        <p className="text-xs text-gray-500 mt-4 text-center">{disabledReason}</p>
      ) : (
        <form onSubmit={send} className="mt-4 space-y-2">
          <textarea value={text} onChange={(e) => setText(e.target.value.slice(0, 2000))} rows={3}
            placeholder={internal ? "Internal note (only staff can see this)…" : "Type your message…"}
            className={`w-full resize-none rounded-xl px-3.5 py-3 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-2 bg-[#141C30] border ${
              internal ? "border-amber-500/40 focus:ring-amber-500/10" : "border-white/10 focus:border-cyan-500/50 focus:ring-cyan-500/10"}`} />
          <div className="flex items-center justify-between gap-2">
            {viewer === "SUPPORT" ? (
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input type="checkbox" className="accent-amber-500" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
                Internal note
              </label>
            ) : <span className="text-[11px] text-gray-600">{text.length}/2000</span>}
            <Button type="submit" size="sm" loading={busy} disabled={!text.trim()}><Send className="w-3.5 h-3.5" /> {internal ? "Add note" : "Send"}</Button>
          </div>
        </form>
      )}
    </div>
  );
}
