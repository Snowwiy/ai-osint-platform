import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ mode }) => ({
  // Desktop builds intentionally ignore local .env files. Only the fixed,
  // local values supplied by desktop/scripts/build.mjs may enter that bundle.
  envDir: mode === "desktop" ? false : undefined,
  plugins: [react()],
}));
