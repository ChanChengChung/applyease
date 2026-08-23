import { defineConfig } from "vite";

export default defineConfig({
  publicDir: "public",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: { popup: "popup.html", background: "src/background.ts", content: "src/content.ts" },
      output: { entryFileNames: "src/[name].js", chunkFileNames: "src/chunks/[name]-[hash].js", assetFileNames: "assets/[name]-[hash][extname]" },
    },
  },
});
