import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
      server: {
        port: 3000,
        host: '0.0.0.0',
        proxy: {
          // In production FastAPI serves /img/* on the same origin. In dev
          // the React app runs on :3000 and the backend on :8000, so proxy
          // /img/* so <img src="/img/..."> resolves to the transform pipeline.
          '/img': 'http://localhost:8000',
        },
      },
      plugins: [react()],
      define: {
        'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
        'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY)
      },
      resolve: {
        alias: {
          '@': path.resolve(__dirname, '.'),
        }
      },
      build: {
        rollupOptions: {
          output: {
            // Friendlier filenames in DevTools
            chunkFileNames: 'assets/[name]-[hash].js',
            entryFileNames: 'assets/[name]-[hash].js',
          },
        },
        chunkSizeWarningLimit: 1000,
        // modulePreload tuning — the source of the persistent
        // "preloaded using link preload but not used" warnings.
        //
        // History:
        //   * `modulePreload: false` (previous setting) — disables the
        //     POLYFILL but Vite STILL ships the `__vitePreload` runtime
        //     helper in the bundle. Every dynamic `import()` (we have 50+
        //     React.lazy routes plus the hover-prefetch in
        //     lib/routePrefetch.ts) runs the helper, which injects
        //     `<link rel="modulepreload" href="...">` for every JS dep of
        //     the chunk being loaded. Each unused preload becomes a
        //     console warning. With shared deps fanning out across many
        //     routes, the count hits 100+ per session.
        //
        // Fix: keep the helper (we need its CSS-loading path for code-
        // split CSS to work) but filter out JS deps. The browser's
        // native ES module loader resolves JS deps through the import
        // graph on demand — losing the modulepreload tag just means
        // dep JS is fetched serially-from-parent instead of in parallel,
        // which is imperceptible for our chunk sizes. CSS deps stay so
        // the styling for lazy routes still preloads in parallel.
        modulePreload: {
          polyfill: false,
          // Vite passes the chunk's filename + its declared deps; we
          // return the deps it should preload. Filter to CSS only.
          resolveDependencies: (_filename: string, deps: string[]) =>
            deps.filter((d) => d.endsWith('.css')),
        },
      },
    };
});
