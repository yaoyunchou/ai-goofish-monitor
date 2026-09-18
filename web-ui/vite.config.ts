/// <reference types="vitest/config" />
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
        const message = err instanceof Error ? err.message : String(err)
        console.error('[vite] proxy error:', message)
      })
    },
  }
}

// 后端地址：默认 8000，可用 BACKEND_PORT 覆盖（本项目本地开发用 8001，避开端口占用）。
const backendPort = process.env.BACKEND_PORT || '8000'
const backendHttp = `http://127.0.0.1:${backendPort}`
const backendWs = `ws://127.0.0.1:${backendPort}`

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
      '/api': proxyWithBackendError(backendHttp),
      '/auth': proxyWithBackendError(backendHttp),
      '/ws': {
        target: backendWs,
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.ts'],
    setupFiles: ['./vitest.setup.ts'],
  },
})
