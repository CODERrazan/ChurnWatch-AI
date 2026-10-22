import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The Monitoring API has no CORS support, so during local development the browser
// calls /monitoring-proxy/... on the Vite server, which forwards to the Monitoring API.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const monitoringTarget = env.VITE_MONITORING_API_BASE_URL || 'http://127.0.0.1:8010'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true, // the Main API only allows origins on ports 5173 and 3000 by default
      proxy: {
        '/monitoring-proxy': {
          target: monitoringTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/monitoring-proxy/, ''),
        },
      },
    },
  }
})
