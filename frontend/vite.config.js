import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/ingest': 'http://127.0.0.1:8000',
      '/tasks': 'http://127.0.0.1:8000',
      '/users': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000'
    }
  }
})
