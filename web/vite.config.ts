import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { mockClaudeProxy } from "./vite-plugins/mock-claude-proxy";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), mockClaudeProxy()],
  base: "/ForgeDS/",
});
