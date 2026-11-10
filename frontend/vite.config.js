import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
      '/sru_logo.png': 'http://127.0.0.1:8000',
      '/sru_ai_voice_assistant_orb.png': 'http://127.0.0.1:8000',
    }
  }
})
