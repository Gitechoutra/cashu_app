import { defineConfig } from "vite";
import path from "path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /v1 to Flask so the browser sees ONE origin: the
// httpOnly refresh cookie (SameSite=Strict) then works without CORS credentials.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/v1": { target: "http://127.0.0.1:5050", changeOrigin: false } },
  },
  test: { environment: "node" },
});
