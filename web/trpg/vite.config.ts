import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 浏览器扩展构建：以 index.html 为 popup 入口；public/ 下的 manifest.json、composition.yml
// 一并拷贝进 dist。base "./" 兼容 file:// 预览与 chrome-extension:// 加载。
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: "index.html",
      },
    },
  },
});
