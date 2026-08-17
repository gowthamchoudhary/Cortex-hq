import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Flask API server runs on CORTEX_API_PORT (default 8000) inside the
// workspace; the Vite dev server proxies /api there so the browser never
// needs to know about a second origin.
const API_TARGET = process.env.CORTEX_API_URL || "http://127.0.0.1:8000";
const PORT = Number(process.env.PORT) || 5173;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: PORT,
    // Replit previews use a generated proxied hostname.
    allowedHosts: true,
    // Freebuff requires HMR to stay disabled in managed dev servers.
    hmr: false,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
