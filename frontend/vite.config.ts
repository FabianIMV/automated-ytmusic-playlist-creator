import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

// Normaliza VITE_BASE ("/", "/repo", "/repo/") a una ruta con "/" al inicio y al final.
function normalizeBase(raw: string | undefined): string {
  const value = (raw ?? '').trim()
  if (!value || value === '/') return '/'
  if (value === './' || /^https?:\/\//.test(value)) return value.endsWith('/') ? value : `${value}/`
  return `/${value.replace(/^\/+|\/+$/g, '')}/`
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    base: normalizeBase(env.VITE_BASE),
    plugins: [react(), tailwindcss()],
    server: {
      // En desarrollo, /api se reenvía al backend FastAPI.
      proxy: {
        '/api': { target: env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
      },
    },
    preview: {
      proxy: {
        '/api': { target: env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
      },
    },
  }
})
