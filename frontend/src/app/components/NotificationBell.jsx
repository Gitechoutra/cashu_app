import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
import { Bell } from "lucide-react";
import { useAuth } from "../context/AuthContext";

/** Bell with unread count; polls gently while the app is visible. */
export function NotificationBell({ to = "/user/notifications" }) {
  const { api } = useAuth();
  const { pathname } = useLocation();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let live = true;
    const load = () => { if (!document.hidden) api("/notifications/unread-count").then((r) => live && r.ok && setUnread(r.data.unread)); };
    load();
    const t = setInterval(load, 60000);
    return () => { live = false; clearInterval(t); };
  }, [api, pathname]);

  return (
    <Link to={to} aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
      className="relative p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5">
      <Bell className="w-4 h-4" />
      {unread > 0 && (
        <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}
