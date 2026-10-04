import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The proxy sends /api/... to your FastAPI backend, so the browser never hits CORS problems.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
    },
  },
})
