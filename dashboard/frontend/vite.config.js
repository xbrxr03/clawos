/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // three-render-objects (used by react-force-graph-3d) imports WebGPURenderer
      // from the three/webgpu subpath export. ClawOS targets WebGL only, so we
      // shim that module to re-export WebGLRenderer under the WebGPURenderer name.
      // This makes the optional WebGPU path silently fall back to WebGL.
      'three/webgpu': path.resolve(__dirname, 'src/shims/three-webgpu.js'),
      'three/tsl': path.resolve(__dirname, 'src/shims/three-webgpu.js'),
    },
  },
  optimizeDeps: {
    exclude: ['three/webgpu', 'three/tsl'],
  },
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
