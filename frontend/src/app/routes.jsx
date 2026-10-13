import { createBrowserRouter, Navigate } from "react-router";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { OnboardingPage } from "./pages/OnboardingPage";
import { SignInPage } from "./pages/SignInPage";
import { StaffLoginPage } from "./pages/StaffLoginPage";
// User (customer)
import { UserLayout } from "./pages/user/UserLayout";
import { UserHome } from "./pages/user/UserHome";
import { UserCards } from "./pages/user/UserCards";
import { CardDetails } from "./pages/user/CardDetails";
import { PayBills } from "./pages/user/PayBills";
import { ScanPay } from "./pages/user/ScanPay";
import { HelpSupport } from "./pages/user/HelpSupport";
import { UserSettings } from "./pages/user/UserSettings";
import { Notifications } from "./pages/user/Notifications";
// Customer Support
import { SupportLayout } from "./pages/support/SupportLayout";
import { SupportTickets } from "./pages/support/SupportTickets";
import { SupportLookup } from "./pages/support/SupportLookup";
// Admin
import { AdminLayout } from "./pages/admin/AdminLayout";
import { AdminDashboard } from "./pages/admin/AdminDashboard";
import { AdminUsers } from "./pages/admin/AdminUsers";
import { AdminPayments } from "./pages/admin/AdminPayments";
import { AdminGateways } from "./pages/admin/AdminGateways";
import { AdminBanks } from "./pages/admin/AdminBanks";
import { AdminAudit } from "./pages/admin/AdminAudit";
import { AdminPlatform } from "./pages/admin/AdminPlatform";
import { AdminReconciliation } from "./pages/admin/AdminReconciliation";

export const router = createBrowserRouter([
  { path: "/", Component: OnboardingPage },
  { path: "/signin", Component: SignInPage },
  { path: "/admin/login", element: <StaffLoginPage role="ADMIN" /> },
  { path: "/support/login", element: <StaffLoginPage role="SUPPORT" /> },
  {
    path: "/user",
    Component: UserLayout,
    errorElement: <ErrorBoundary />,
    children: [
      { index: true, Component: UserHome },
      { path: "cards", Component: UserCards },
      { path: "cards/:cardId", Component: CardDetails },
      { path: "bills", Component: PayBills },
      { path: "scan", Component: ScanPay },
      { path: "help", Component: HelpSupport },
      { path: "notifications", Component: Notifications },
      { path: "settings", Component: UserSettings },
    ],
  },
  {
    path: "/support",
    Component: SupportLayout,
    errorElement: <ErrorBoundary />,
    children: [
      { index: true, Component: SupportTickets },
      { path: "lookup", Component: SupportLookup },
      { path: "settings", Component: UserSettings },
    ],
  },
  {
    path: "/admin",
    Component: AdminLayout,
    errorElement: <ErrorBoundary />,
    children: [
      { index: true, Component: AdminDashboard },
      { path: "users", Component: AdminUsers },
      { path: "payments", Component: AdminPayments },
      { path: "tickets", Component: SupportTickets },
      { path: "gateways", Component: AdminGateways },
      { path: "banks", Component: AdminBanks },
      { path: "audit", Component: AdminAudit },
      { path: "platform", Component: AdminPlatform },
      { path: "reconciliation", Component: AdminReconciliation },
      { path: "settings", Component: UserSettings },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
