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
      '/api': 'http://localhost:8000',
      '/pages': 'http://localhost:8000',
      '/search': 'http://localhost:8000',
      '/query': 'http://localhost:8000',
      '/lint': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
      '/cost': 'http://localhost:8000',
      '/cron': 'http://localhost:8000',
      '/index': 'http://localhost:8000',
      '/log': 'http://localhost:8000',
      '/export': 'http://localhost:8000',
      '/recompile': 'http://localhost:8000',
      '/data': 'http://localhost:8000',
      '/docs': 'http://localhost:8000',
    },
  },
  build: {
    outDir: '../src/sagemate/api/static/dist',
    emptyOutDir: true,
  },
}))
