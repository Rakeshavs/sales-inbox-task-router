import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/ingest': 'http://localhost:8000',
      '/tasks': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/api': 'http://localhost:8000'
    }
  }
})
