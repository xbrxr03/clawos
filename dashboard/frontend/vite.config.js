import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:7070',
      '/ws': { target: 'ws://localhost:7070', ws: true },
    },
  },
  build: {
    outDir: '../../services/dashd/static',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react-router-dom')) return 'router'
            return 'vendor'
          }

          if (id.includes('src/pages/pages.jsx')) return 'command-center-pages'
          if (id.includes('src/pages/Workflows')) return 'workflows'
          if (id.includes('src/pages/Settings')) return 'settings'
          if (id.includes('src/pages/setup/')) return 'setup'
          return undefined
        },
      },
    },
  },
})
