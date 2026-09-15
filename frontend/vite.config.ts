import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        // Use the IPv4 loopback: "localhost" may resolve to ::1 while Flask
        // binds to 127.0.0.1, which breaks the proxy on Windows.
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
});
