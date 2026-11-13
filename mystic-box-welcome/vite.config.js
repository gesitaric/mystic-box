import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// As imagens das cartas e o mapa-múndi vêm do jogo (../mystic-box/src/assets),
// para não manter cópias. O servidor de desenvolvimento precisa ler a pasta de cima.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    fs: { allow: ['..'] },
  },
})
