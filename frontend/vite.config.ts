import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  resolve: mode === "fixture" ? {
    alias: {
      "./fixtureBoundary.ts": decodeURIComponent(
        new URL("./src/api/fixtureBoundary.fixture.ts", import.meta.url).pathname,
      ),
    },
  } : undefined,
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
}));
