import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const apiPaths = ['/properties', '/chat', '/reviews'];

export default defineConfig({
  base: '/ui/',
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(apiPaths.map((p) => [p, 'http://localhost:8000'])),
  },
});
