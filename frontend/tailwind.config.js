/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        beige: '#EAE3D2',
        olive: '#6E7455',
        terracotta: '#C2603A',
        charcoal: '#2A2723',
        'beige-card': '#DCD6BE',
      },
      fontFamily: {
        // 'serif' is kept as the display alias so every existing font-serif class
        // keeps working; it now resolves to a geometric sans that suits glass.
        display: ['"Space Grotesk"', 'Inter', 'sans-serif'],
        serif: ['"Space Grotesk"', 'Inter', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
