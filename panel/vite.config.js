// Panel M&A (ADR 0003, 0015, 0029). Lo sirve la API en /admin/ con enrutado por hash.
// Build compatible con la CSP del panel: sin scripts ni estilos en línea y sin source maps.
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/admin/',
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    modulePreload: { polyfill: false },
    assetsInlineLimit: 0, // nada como data: (fuentes e imágenes como archivos)
    cssCodeSplit: false,
  },
  server: { host: '0.0.0.0', port: 5173 },
  test: {
    environment: 'jsdom',
    include: ['test/**/*.test.{js,jsx}'],
    setupFiles: ['test/preparar.js'],
  },
})
