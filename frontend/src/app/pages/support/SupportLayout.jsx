import { Inbox, Search, Settings } from "lucide-react";
import { AppShell } from "../../components/AppShell";

const NAV = [
  { to: "/support", label: "Tickets", icon: Inbox, end: true },
  { to: "/support/lookup", label: "Lookup", icon: Search },
  { to: "/support/settings", label: "Settings", icon: Settings, mobile: false },
];

/** Customer Support (SUPPORT role) area. */
export function SupportLayout() {
  return <AppShell role="SUPPORT" nav={NAV} accent="violet" settingsPath="/support/settings" />;
}
