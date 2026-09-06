import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 前端固定使用 5175 端口，与后端 CORS 白名单保持一致。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    strictPort: true,
  },
})
