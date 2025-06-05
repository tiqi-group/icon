import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import svgr from "vite-plugin-svgr";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), svgr()],
  build: {
    outDir: "../src/icon/server/frontend",
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
