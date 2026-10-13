/**
 * context/AuthContext.jsx
 * =======================
 * Session state machine + the authenticated `api()` helper every screen uses.
 *
 *   loading → signed_out | locked
 *   signed_out → (OTP verified) → onboarding | ready
 *   locked → (PIN / biometric) → ready
 *   ready → (idle / app hidden / server APP_LOCKED) → locked
 *
 * The access token lives ONLY in memory (never localStorage). The long-lived
 * refresh token is an httpOnly cookie the JS cannot read.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { getAssertion, isBiometricAvailable } from "../utils/webauthn";

export const API_BASE = "/v1";
const CSRF = { "X-Requested-With": "cardvault" };

/** Random per-browser id used to recognise devices (server stores only a hash). */
export function deviceId() {
  try {
    let id = localStorage.getItem("cv_device_id");
    if (!id || !/^[A-Za-z0-9_-]{16,64}$/.test(id)) {
      const bytes = crypto.getRandomValues(new Uint8Array(18));
      id = "web-" + Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
      localStorage.setItem("cv_device_id", id);
    }
    return id;
  } catch {
    return undefined;   // storage blocked: the server simply skips device binding
  }
}
const deviceHeader = () => { const d = deviceId(); return d ? { "X-Device-Id": d } : {}; };
const IDLE_LOCK_MS = 15 * 60 * 1000;          // mirrors SESSION_IDLE_LOCK_MINUTES
const HIDDEN_LOCK_MS = 2 * 60 * 1000;         // lock when the app is backgrounded this long
const REFRESH_EVERY_MS = 12 * 60 * 1000;      // under the 15-min access-token lifetime

const AuthContext = createContext(null);

async function parse(res) {
  let body = null;
  try { body = await res.json(); } catch { /* non-JSON */ }
  return {
    ok: res.ok && body?.bool !== false,
    status: res.status,
    data: body?.response ?? {},
    message: body?.response?.message || (res.ok ? "" : "Something went wrong. Please try again."),
    code: body?.response?.code,
    errors: body?.response?.errors || {},
  };
}

export async function publicPost(path, body) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...CSRF, ...deviceHeader() }, body: JSON.stringify(body || {}),
    });
    return parse(res);
  } catch {
    return { ok: false, status: 0, data: {}, message: "Network error. Check your connection.", errors: {} };
  }
}

export function AuthProvider({ children }) {
  const [status, setStatus] = useState("loading");
  const [user, setUser] = useState(null);
  const [lockInfo, setLockInfo] = useState(null);
  const tokenRef = useRef(null);
  const refreshPromise = useRef(null);
  const lastActivity = useRef(Date.now());
  const hiddenAt = useRef(null);

  const setSession = useCallback((data) => {
    tokenRef.current = data.access_token;
    setUser(data.user);
    lastActivity.current = Date.now();
    const u = data.user || {};
    setStatus(!u.full_name || !u.has_pin || u.pin_reset_required ? "onboarding" : "ready");
  }, []);

  const toSignedOut = useCallback(() => {
    tokenRef.current = null;
    setUser(null);
    setLockInfo(null);
    setStatus("signed_out");
  }, []);

  const lock = useCallback(async () => {
    tokenRef.current = null;
    const r = await fetch(`${API_BASE}/authentication/session`, { headers: CSRF }).then(parse).catch(() => null);
    if (r?.data?.has_session && r.data.user?.has_pin) {
      setLockInfo(r.data.user);
      setStatus("locked");
    } else {
      toSignedOut();
    }
  }, [toSignedOut]);

  // ── Boot: is there a session on this device? → lock screen, else sign-in ──
  useEffect(() => {
    (async () => {
      const r = await fetch(`${API_BASE}/authentication/session`, { headers: CSRF }).then(parse).catch(() => null);
      if (!r?.data?.has_session) return toSignedOut();
      if (!r.data.user?.has_pin) {
        // Signed in but never finished onboarding: a refresh lets them continue.
        const ref = await publicPost("/authentication/refresh");
        return ref.ok ? setSession(ref.data) : toSignedOut();
      }
      setLockInfo(r.data.user);
      setStatus("locked");
    })();
  }, [setSession, toSignedOut]);

  // ── Single-flight silent refresh ──
  const refresh = useCallback(async () => {
    if (!refreshPromise.current) {
      refreshPromise.current = publicPost("/authentication/refresh").then((r) => {
        refreshPromise.current = null;
        if (r.ok) { tokenRef.current = r.data.access_token; setUser(r.data.user); return true; }
        if (r.code === "APP_LOCKED") lock(); else if (r.status === 401) toSignedOut();
        return false;
      });
    }
    return refreshPromise.current;
  }, [lock, toSignedOut]);

  // ── Authenticated API call with one transparent retry after refresh ──
  const api = useCallback(async (path, { method = "GET", body, signal } = {}, retried = false) => {
    let res;
    try {
      res = await fetch(`${API_BASE}${path}`, {
        method, signal, credentials: "same-origin",
        headers: { "Content-Type": "application/json", ...deviceHeader(), ...(tokenRef.current ? { Authorization: `Bearer ${tokenRef.current}` } : {}) },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      if (e?.name === "AbortError") throw e;
      return { ok: false, status: 0, data: {}, message: "Network error. Check your connection.", errors: {} };
    }
    const r = await parse(res);
    if (res.status === 401 && !retried) {
      if (["TOKEN_EXPIRED", "AUTH_REQUIRED", "TOKEN_INVALID"].includes(r.code) && (await refresh())) {
        return api(path, { method, body, signal }, true);
      }
      if (r.code === "APP_LOCKED") lock();
      else if (r.code === "SESSION_ENDED") toSignedOut();
    }
    return r;
  }, [refresh, lock, toSignedOut]);

  // ── Activity tracking, idle lock, background lock, proactive refresh ──
  useEffect(() => {
    if (status !== "ready" && status !== "onboarding") return;
    const bump = () => { lastActivity.current = Date.now(); };
    const onVis = () => {
      if (document.hidden) { hiddenAt.current = Date.now(); return; }
      if (status === "ready" && hiddenAt.current && Date.now() - hiddenAt.current > HIDDEN_LOCK_MS) lock();
      hiddenAt.current = null;
    };
    const evts = ["pointerdown", "keydown", "scroll", "touchstart"];
    evts.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    document.addEventListener("visibilitychange", onVis);
    const tick = setInterval(() => {
      if (status === "ready" && Date.now() - lastActivity.current > IDLE_LOCK_MS) lock();
    }, 30 * 1000);
    const ref = setInterval(() => {
      if (Date.now() - lastActivity.current < IDLE_LOCK_MS) refresh();
    }, REFRESH_EVERY_MS);
    return () => {
      evts.forEach((e) => window.removeEventListener(e, bump));
      document.removeEventListener("visibilitychange", onVis);
      clearInterval(tick); clearInterval(ref);
    };
  }, [status, lock, refresh]);

  // ── Unlock ──
  const unlockWithPin = useCallback(async (pin) => {
    const r = await publicPost("/authentication/unlock", { pin });
    if (r.ok) setSession(r.data);
    else if (r.code === "SESSION_ENDED" || r.code === "NO_SESSION") toSignedOut();
    return r;
  }, [setSession, toSignedOut]);

  const unlockWithBiometric = useCallback(async () => {
    const opt = await publicPost("/authentication/webauthn/options");
    if (!opt.ok) return opt;
    let credential;
    try { credential = await getAssertion(opt.data.options); }
    catch { return { ok: false, message: "Biometric check was cancelled. Use your PIN." }; }
    const r = await publicPost("/authentication/webauthn/verify", { credential });
    if (r.ok) setSession(r.data);
    return r;
  }, [setSession]);

  /** Admin / Customer Support: email + 6-digit PIN, no OTP. `role` limits which role may sign in on that page. */
  const staffLogin = useCallback(async (email, pin, role) => {
    const r = await publicPost("/authentication/staff/login", { email, pin, role });
    if (r.ok) setSession(r.data);
    return r;
  }, [setSession]);

  /** OTP verified for an account that has a PIN: the server session is locked until the PIN is entered. */
  const requireUnlock = useCallback((info) => {
    tokenRef.current = null;
    setLockInfo(info);
    setStatus("locked");
  }, []);

  const logout = useCallback(async () => {
    await publicPost("/authentication/logout");
    toSignedOut();
  }, [toSignedOut]);

  const finishOnboarding = useCallback((patch) => {
    setUser((u) => {
      const next = { ...u, ...patch };
      if (next.full_name && next.has_pin && !next.pin_reset_required) setStatus("ready");
      return next;
    });
  }, []);

  const value = useMemo(() => ({
    status, user, lockInfo, api, setSession, lock, logout, unlockWithPin, unlockWithBiometric,
    finishOnboarding, setUser, isBiometricAvailable, staffLogin, requireUnlock,
  }), [status, user, lockInfo, api, setSession, lock, logout, unlockWithPin, unlockWithBiometric, finishOnboarding, staffLogin, requireUnlock]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
