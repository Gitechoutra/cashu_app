import { Component } from "react";
import { useRouteError } from "react-router";

function Fallback({ onRetry }) {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-6">
      <h2 className="text-lg font-semibold text-white">Something went wrong</h2>
      <p className="text-sm text-gray-500 mt-1">Please reload the page. Your data is safe.</p>
      <button onClick={onRetry} className="mt-4 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200 hover:bg-white/10">Reload</button>
    </div>
  );
}

/** Router errorElement (uses the route error) — details are logged, never shown. */
export function ErrorBoundary() {
  const error = useRouteError();
  console.error(error);
  return <Fallback onRetry={() => window.location.reload()} />;
}

/** Class boundary for render errors outside the router. */
export class AppErrorBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(err) { console.error(err); }
  render() { return this.state.failed ? <Fallback onRetry={() => window.location.reload()} /> : this.props.children; }
}
