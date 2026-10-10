import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard runs on http://localhost:5173 and talks to the FastAPI backend
// at http://localhost:8000 (see src/api.ts and .env).
export default defineConfig({
  plugins: [react()],
  // 127.0.0.1 avoids clashing with another app on localhost:5173; if 5173 is busy Vite picks the next free port
  // (the backend allows any localhost port).
  server: { host: "127.0.0.1", port: 5173 },
});
