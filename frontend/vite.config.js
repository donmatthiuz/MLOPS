import { defineConfig } from 'vite'

const apiTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8007'

export default defineConfig({
  server: {
    proxy: Object.fromEntries(
      ['/health', '/precios', '/prediccion', '/modelo', '/docs', '/openapi.json'].map((path) => [
        path,
        { target: apiTarget, changeOrigin: true },
      ]),
    ),
  },
})
