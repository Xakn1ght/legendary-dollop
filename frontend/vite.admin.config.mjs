import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Admin panel React build. Separate from the user dashboard build so the two
// lanes never clobber each other's output. Lands in the aiohttp admin static
// mount (/admin/react/) — the shell handlers point /admin/ + /admin/support at
// react/index.html + react/support.html.
export default defineConfig({
  plugins: [react()],
  base: '/admin/react/',
  build: {
    outDir: fileURLToPath(new URL('../src/app/webapp/admin/react', import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: fileURLToPath(new URL('./admin.html', import.meta.url)),
        support: fileURLToPath(new URL('./admin-support.html', import.meta.url)),
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8585',
      '/admin/admin.css': 'http://localhost:8585',
      '/admin/admin-fx.js': 'http://localhost:8585',
      '/admin/admin_customizer.js': 'http://localhost:8585',
    },
  },
});
