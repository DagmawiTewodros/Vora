import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Vora Addis HMS",
        short_name: "Vora HMS",
        description: "Hotel management for Vora Addis: front desk, POS, housekeeping, billing.",
        theme_color: "#7a4b2a",
        background_color: "#faf7f2",
        display: "standalone",
        start_url: "/",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/admin\//],
        runtimeCaching: [
          {
            // Menus, rooms and the front desk board stay readable when the internet drops.
            urlPattern: ({ url }) =>
              /^\/api\/(pos\/(menu|outlets|categories)|rooms|room-types|front-desk|settings|housekeeping\/rooms|calendar)\/?/.test(url.pathname),
            handler: "NetworkFirst",
            method: "GET",
            options: { cacheName: "vora-api", networkTimeoutSeconds: 4, expiration: { maxEntries: 200, maxAgeSeconds: 86400 } },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/admin": "http://127.0.0.1:8000",
      "/static": "http://127.0.0.1:8000",
    },
  },
});
