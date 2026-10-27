/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // A simulated browser DOM, so components can render inside Node.
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
