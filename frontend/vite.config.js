import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the Vite server proxies /api to the FastAPI backend, so the browser
// talks to a single origin (no CORS needed). In production the backend serves the build.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
    },
  },
})
