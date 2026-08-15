import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

// Separate from Next.js's own Turbopack build — vitest runs components and
// pure lib functions in isolation via Vite, per CLAUDE.md §7's definition
// of done ("vitest covers components/hooks; use playwright for
// route-level/e2e checks if added later").
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
