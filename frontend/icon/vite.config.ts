import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import svgr from "vite-plugin-svgr";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), svgr()],
  server: {
    proxy: {
      // The sequence visualiser is served by the ICON backend (see
      // src/icon/server/web_server/visualiser.py).
      "/visualizer": "http://localhost:8004",
    },
  },
  build: {
    outDir: "../../src/icon/server/frontend",
    rollupOptions: {
      output: {
        // located large chunks using https://www.npmjs.com/package/rollup-plugin-visualizer
        manualChunks: {
          zrender: ["zrender"],
          echarts: ["echarts"],
          mui: ["@mui/material"],
        },
      },
    },
  },
  esbuild: {
    pure: ["console.log"],
  },
});
