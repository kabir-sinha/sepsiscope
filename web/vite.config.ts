import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Bind dev/preview servers to loopback only (never the LAN).
  // /api is forwarded to the local demo API (sepsiscope demo serve, 127.0.0.1:8000),
  // so the page itself never calls another origin.
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  preview: { host: '127.0.0.1' },
  // No source maps in the build (nothing of the source tree is shipped).
  build: { sourcemap: false },
})
