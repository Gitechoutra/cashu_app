import { useEffect, useState } from "react";
import { API_BASE } from "../context/AuthContext";

let cache = null;
let inflight = null;

/** Public platform settings (maintenance banner, support hours). Cached per page load. */
export function usePlatformSettings() {
  const [settings, setSettings] = useState(cache || {});
  useEffect(() => {
    if (cache) return;
    inflight = inflight || fetch(`${API_BASE}/platform/settings`).then((r) => r.json()).then((d) => (cache = d?.response || {}))
      .catch(() => ({}));
    let live = true;
    inflight.then((s) => live && setSettings(s || {}));
    return () => { live = false; };
  }, []);
  return settings;
}
