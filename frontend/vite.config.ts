import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/icon/server/frontend",
  },
  esbuild: {
    drop: ["console", "debugger"],
  },
});
