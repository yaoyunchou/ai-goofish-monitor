import type { ServerResponse } from 'http'
import { defineConfig, type ProxyOptions } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

function proxyWithBackendError(target: string): ProxyOptions {
  return {
    target,
    changeOrigin: true,
    configure(proxy) {
      proxy.on('error', (err, _req, res) => {
        const response = res as ServerResponse | undefined
        if (response && !response.headersSent) {
          response.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
          response.end(
            JSON.stringify({
              detail: '后端未启动，请先运行 python -m src.app（或 VS Code F5 Backend）',
            }),
          )
        }
        console.error('[vite] proxy error:', err.message)
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: path.resolve(__dirname, '../dist'),
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': proxyWithBackendError('http://127.0.0.1:8000'),
      '/auth': proxyWithBackendError('http://127.0.0.1:8000'),
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})
