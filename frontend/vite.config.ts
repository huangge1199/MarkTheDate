import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    // 监听 127.0.0.1 而不是 0.0.0.0，避免在受限 Windows 环境下 EACCES
    // 如果需要局域网/容器访问，改回 '0.0.0.0' 即可
    host: '127.0.0.1',
    strictPort: false, // 端口被占时自动切换到下一个可用端口
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})