import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// TST_API_URL lets the Playwright smoke test point the proxy at its own API server.
const apiUrl = process.env.TST_API_URL ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': apiUrl,
    },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
