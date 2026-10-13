import { Link, NavLink, Navigate, Outlet } from "react-router";
import { AlertTriangle, Lock, LogOut, Settings } from "lucide-react";
import { NotificationBell } from "./NotificationBell";
import { usePlatformSettings } from "../hooks/usePlatform";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../pages/OnboardingPage";
import { ROLE_LABEL, homeFor, loginFor } from "../utils/roles";

/**
 * Signed-in layout shared by every role: sidebar on desktop, top bar + bottom
 * nav on mobile. `role` guards the area — a signed-in user with a different role
 * is sent to their own home (the API rejects them anyway).
 *
 * nav items: { to, label, icon, end?, mobile?: boolean, primary?: boolean }
 * `primary` renders the raised centre button in the mobile bar (e.g. Scan).
 */
export function AppShell({ role, nav, accent = "cyan", settingsPath }) {
  const { status, user, lock, logout } = useAuth();
  const platform = usePlatformSettings();
  if (status === "signed_out" || status === "onboarding") return <Navigate to={loginFor(role)} replace />;
  if (status !== "ready") return null;
  if (user?.role !== role) return <Navigate to={homeFor(user?.role)} replace />;

  const initials = (user?.full_name || "U").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  const mobileNav = nav.filter((n) => n.mobile !== false).slice(0, 5);
  const tone = accent === "violet"
    ? { active: "bg-violet-500/10 text-violet-200 border-violet-500/25", text: "text-violet-300", badge: "bg-violet-500/15 text-violet-200 border-violet-500/25" }
    : accent === "amber"
      ? { active: "bg-amber-500/10 text-amber-100 border-amber-500/25", text: "text-amber-300", badge: "bg-amber-500/15 text-amber-100 border-amber-500/25" }
      : { active: "bg-cyan-500/10 text-cyan-200 border-cyan-500/20", text: "text-cyan-300", badge: "bg-cyan-500/10 text-cyan-200 border-cyan-500/20" };

  return (
    <div className="min-h-screen bg-[#070B14] text-gray-200 lg:flex">
      <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-white/5 bg-[#0A0F1C] sticky top-0 h-screen overflow-y-auto no-scrollbar p-5 [@media(max-height:820px)]:py-3">
        <Logo />
        {role !== "USER" && (
          <span className={`mt-3 self-start text-[10px] uppercase tracking-[0.16em] px-2 py-1 rounded-md border ${tone.badge}`}>{ROLE_LABEL[role]}</span>
        )}
        <nav className="mt-7 [@media(max-height:820px)]:mt-4 space-y-1 [@media(max-height:820px)]:space-y-0.5 flex-1 min-h-0 overflow-y-auto no-scrollbar">
          {nav.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => `flex items-center gap-3 px-3 py-2.5 [@media(max-height:820px)]:py-2 rounded-xl text-sm border transition-colors ${
                isActive ? tone.active : "text-gray-400 hover:text-white hover:bg-white/5 border-transparent"}`}>
              <n.icon className="w-4 h-4" /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/5 pt-4 space-y-1 shrink-0">
          <div className="flex items-center gap-3 px-2 py-2">
            {role === "USER" && <NotificationBell />}
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-cyan-500/30 to-blue-600/30 border border-white/10 flex items-center justify-center text-xs font-semibold text-white">{initials}</div>
            <div className="min-w-0">
              <div className="text-sm text-white truncate">{user?.full_name}</div>
              <div className="text-[11px] text-gray-500 truncate">{user?.mobile_number}</div>
            </div>
          </div>
          <button onClick={lock} className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-400 hover:text-white hover:bg-white/5"><Lock className="w-4 h-4" /> Lock app</button>
          <button onClick={logout} className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-400 hover:text-red-300 hover:bg-red-500/5"><LogOut className="w-4 h-4" /> Sign out</button>
        </div>
      </aside>

      <header className="lg:hidden sticky top-0 z-40 flex items-center justify-between px-4 h-14 bg-[#070B14]/90 backdrop-blur border-b border-white/5">
        <div className="flex items-center gap-2">
          <Logo />
          {role !== "USER" && <span className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border ${tone.badge}`}>{ROLE_LABEL[role]}</span>}
        </div>
        <div className="flex items-center gap-1">
          {role === "USER" && <NotificationBell />}
          {settingsPath && (
            <Link to={settingsPath} aria-label="Settings" className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5"><Settings className="w-4 h-4" /></Link>
          )}
          <button onClick={lock} aria-label="Lock app" className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5"><Lock className="w-4 h-4" /></button>
          <button onClick={logout} aria-label="Sign out" className="p-2 rounded-lg text-gray-400 hover:text-red-300 hover:bg-white/5"><LogOut className="w-4 h-4" /></button>
        </div>
      </header>

      <main className="flex-1 min-w-0 pb-24 lg:pb-0">
        {platform.MAINTENANCE_MESSAGE && (
          <div role="status" className="flex items-center gap-2 px-4 py-2.5 text-sm bg-amber-500/10 border-b border-amber-500/20 text-amber-100">
            <AlertTriangle className="w-4 h-4 shrink-0" /> {platform.MAINTENANCE_MESSAGE}
          </div>
        )}
        <Outlet />
      </main>

      <nav className="grid lg:hidden fixed bottom-0 inset-x-0 z-40 bg-[#0A0F1C]/95 backdrop-blur border-t border-white/5 pb-[env(safe-area-inset-bottom)]"
        style={{ gridTemplateColumns: `repeat(${mobileNav.length}, minmax(0, 1fr))` }}>
        {mobileNav.map((n) => n.primary ? (
          <NavLink key={n.to} to={n.to} className="flex flex-col items-center -mt-5 pb-1.5" aria-label={n.label}>
            <span className="w-14 h-14 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 shadow-lg shadow-cyan-500/30 ring-4 ring-[#070B14] flex items-center justify-center">
              <n.icon className="w-6 h-6 text-white" />
            </span>
            <span className="text-[11px] text-gray-300 mt-1">{n.label}</span>
          </NavLink>
        ) : (
          <NavLink key={n.to} to={n.to} end={n.end}
            className={({ isActive }) => `flex flex-col items-center gap-1 py-2.5 text-[11px] ${isActive ? tone.text : "text-gray-500"}`}>
            <n.icon className="w-5 h-5" /> <span className="truncate max-w-full px-1">{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
