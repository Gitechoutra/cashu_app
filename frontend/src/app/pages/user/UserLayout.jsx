import { CreditCard, Headset, Home, IndianRupee, ScanLine, Settings } from "lucide-react";
import { AppShell } from "../../components/AppShell";

const NAV = [
  { to: "/user", label: "Home", icon: Home, end: true },
  { to: "/user/cards", label: "Cards", icon: CreditCard },
  { to: "/user/scan", label: "Scan & Pay", icon: ScanLine, primary: true },
  { to: "/user/bills", label: "Pay Bills", icon: IndianRupee },
  { to: "/user/help", label: "Support", icon: Headset },
  { to: "/user/settings", label: "Settings", icon: Settings, mobile: false },
];

/** Customer (USER role) area. */
export function UserLayout() {
  return <AppShell role="USER" nav={NAV} settingsPath="/user/settings" />;
}
