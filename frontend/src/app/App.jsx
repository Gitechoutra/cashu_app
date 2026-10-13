import { RouterProvider } from "react-router";
import { Loader2 } from "lucide-react";
import { router } from "./routes";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AppLock } from "./components/AppLock";
import { AppErrorBoundary } from "./components/ErrorBoundary";
import { ToastProvider } from "./components/ui";

function Shell() {
  const { status } = useAuth();
  if (status === "loading") {
    return <div className="min-h-screen flex items-center justify-center bg-[#070B14]"><Loader2 className="w-6 h-6 text-cyan-400 animate-spin" /></div>;
  }
  return (
    <>
      {/* Routes stay mounted under the lock so the user returns exactly where they were. */}
      <div aria-hidden={status === "locked"} className={status === "locked" ? "invisible" : ""}>
        <RouterProvider router={router} />
      </div>
      {status === "locked" && <AppLock />}
    </>
  );
}

export default function App() {
  return (
    <AppErrorBoundary>
      <ToastProvider>
        <AuthProvider>
          <Shell />
        </AuthProvider>
      </ToastProvider>
    </AppErrorBoundary>
  );
}
