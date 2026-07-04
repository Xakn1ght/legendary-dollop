import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Build output lands inside the aiohttp static mount (/webapp/dashboard/react/)
// so the backend serves it with zero extra route registration.
export default defineConfig({
  plugins: [react()],
  base: '/webapp/dashboard/react/',
  build: {
    outDir: fileURLToPath(new URL('../src/app/webapp/dashboard/react', import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: fileURLToPath(new URL('./index.html', import.meta.url)),
        charge: fileURLToPath(new URL('./charge.html', import.meta.url)),
        purchase: fileURLToPath(new URL('./purchase.html', import.meta.url)),
        support: fileURLToPath(new URL('./support.html', import.meta.url)),
      },
    },
  },
  // Dev: `npm run dev` proxies shared legacy assets + API to the running bot webserver.
  server: {
    proxy: {
      '/api': 'http://localhost:8585',
      '/webapp': 'http://localhost:8585',
    },
  },
});
