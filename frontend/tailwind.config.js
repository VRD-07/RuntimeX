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
        fraunces: ['Fraunces', 'serif'],
        serif: ['Fraunces', 'serif'],
        sans: ['Inter', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
