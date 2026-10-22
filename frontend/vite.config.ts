import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendUrl = env.BACKEND_URL || 'http://localhost:8000';

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      strictPort: false,
      proxy: {
        // Same-origin proxy: the browser only ever talks to the Vite dev
        // server, so the HttpOnly session cookie (SameSite=Lax) is sent
        // automatically and the CSRF double-submit token keeps working.
        '/api': {
          target: backendUrl,
          changeOrigin: true,
          secure: false,
        },
        '/docs': { target: backendUrl, changeOrigin: true },
        '/openapi.json': { target: backendUrl, changeOrigin: true },
      },
    },
    preview: {
      port: 4173,
    },
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
      chunkSizeWarningLimit: 900,
      rollupOptions: {
        output: {
          manualChunks: {
            react: ['react', 'react-dom', 'react-router-dom'],
            charts: ['recharts'],
            forms: ['react-hook-form', '@hookform/resolvers', 'zod'],
          },
        },
      },
    },
  };
});
