import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

/**
 * PR-3 Vitest configuration.
 *
 * Reuses the project's `@vitejs/plugin-vue` to compile `.vue` SFCs at test time,
 * and aliases `@/...` to `src/...` matching the main vite.config.ts.
 *
 * Tests run in `node` environment by default; components that need a DOM use
 * `// @vitest-environment jsdom` or `happy-dom` directives (if/when added).
 *
 * Note: `@vue/test-utils`, `jsdom`, and `happy-dom` are NOT installed in this
 * project, so component tests in this suite rely on programmatic Vue runtime
 * (defineComponent + createApp + createElementVNode) instead of DOM assertions.
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  test: {
    include: [
      'src/**/*.spec.ts',
      'src/**/__tests__/**/*.spec.ts',
    ],
    environment: 'node',
  },
})