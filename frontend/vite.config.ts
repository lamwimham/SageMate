import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import { TanStackRouterVite } from '@tanstack/router-plugin/vite'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ command }) => ({
  base: command === 'serve' ? '/' : '/static/dist/',
  plugins: [
    tailwindcss(),
    TanStackRouterVite({ target: 'react', autoCodeSplitting: true }),
    react(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/pages': { target: 'http://localhost:8000', changeOrigin: true },
      '/search': { target: 'http://localhost:8000', changeOrigin: true },
      '/query': { target: 'http://localhost:8000', changeOrigin: true },
      '/lint': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
      '/stats': { target: 'http://localhost:8000', changeOrigin: true },
      '/cost': { target: 'http://localhost:8000', changeOrigin: true },
      '/cron': { target: 'http://localhost:8000', changeOrigin: true },
      '/index': { target: 'http://localhost:8000', changeOrigin: true },
      '/log': { target: 'http://localhost:8000', changeOrigin: true },
      '/export': { target: 'http://localhost:8000', changeOrigin: true },
      '/recompile': { target: 'http://localhost:8000', changeOrigin: true },
      '/data': { target: 'http://localhost:8000', changeOrigin: true },
      '/docs': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: '../src/sagemate/api/static/dist',
    emptyOutDir: true,
  },
}))
