import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // ECharts is intentionally isolated behind the lazy Performance view/chart chunk.
    chunkSizeWarningLimit: 700
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:1964"
    }
  }
});
