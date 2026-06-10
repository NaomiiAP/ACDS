import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'child_process'

function wslBackendHost() {
  try {
    const ip = execSync('wsl hostname -I', { encoding: 'utf8' }).trim().split(/\s+/)[0]
    if (ip) return `http://${ip}:8000`
  } catch {
    /* not on Windows or wsl unavailable */
  }
  return 'http://127.0.0.1:8000'
}

const backendTarget = process.env.VITE_DEV_BACKEND || wslBackendHost()
const graphTarget = process.env.VITE_DEV_GRAPH || backendTarget.replace(':8000', ':8100')

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api/graph': { target: graphTarget, changeOrigin: true },
      '/api': { target: backendTarget, changeOrigin: true },
      '/ws': { target: backendTarget, ws: true, changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('lucide-react')) return 'icons'
            if (id.includes('recharts')) return 'charts'
            return 'vendor'
          }
        },
      },
    },
  },
})
