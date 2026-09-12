import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/adsb': {
        target: 'https://api.adsb.lol',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/adsb/, ''),
      },
      '/fr24': {
        target: 'https://fr24api.flightradar24.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/fr24/, ''),
      },
      '/opensky-auth': {
        target: 'https://auth.opensky-network.org',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/opensky-auth/, ''),
      },
      '/opensky': {
        target: 'https://opensky-network.org',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/opensky/, ''),
      },
      '/adsbdb': {
        target: 'https://api.adsbdb.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/adsbdb/, ''),
      },
    },
  },
})
