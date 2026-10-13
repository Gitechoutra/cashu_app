import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";

/** Loads the user's cards + portfolio summary. One in-flight request at a time;
 *  stale responses from a previous load are ignored. */
export function useCards() {
  const { api } = useAuth();
  const [state, setState] = useState({ cards: [], summary: null, loading: true, error: "" });
  const ctrl = useRef(null);

  const reload = useCallback(async () => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setState((s) => ({ ...s, loading: true, error: "" }));
    try {
      const r = await api("/cards", { signal: c.signal });
      if (c.signal.aborted) return;
      setState(r.ok
        ? { cards: r.data.cards, summary: r.data.summary, loading: false, error: "" }
        : (s) => ({ ...s, loading: false, error: r.message }));
    } catch { /* aborted */ }
  }, [api]);

  useEffect(() => { reload(); return () => ctrl.current?.abort(); }, [reload]);
  return { ...state, reload };
}
