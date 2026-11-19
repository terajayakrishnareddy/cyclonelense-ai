import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxy = { '/api': { target: env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true } };
  return {
    plugins: [react()],
    server: { proxy },
    preview: { proxy },
    build: { chunkSizeWarningLimit: 1200 },
    test: { environment: 'jsdom', globals: true, setupFiles: './src/test/setup.js', css: false, env: { VITE_API_URL: '', VITE_TILE_URL: '' } },
  };
});
