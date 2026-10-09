import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Bind dev/preview servers to loopback only (never the LAN).
  server: { host: '127.0.0.1' },
  preview: { host: '127.0.0.1' },
})
