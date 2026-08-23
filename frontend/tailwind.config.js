/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // The original warm editorial palette, kept and extended rather than replaced.
        beige: '#EAE3D2',
        'beige-card': '#DCD6BE',
        sand: '#F4EFE3',
        olive: '#6E7455',
        terracotta: '#C2603A',
        charcoal: '#2A2723',

        // Semantic aliases used by the new dashboard.
        ink: '#2A2723',
        clay: {
          DEFAULT: '#C2603A',
          deep: '#9E4526',
          soft: '#E2A483',
        },
        moss: {
          DEFAULT: '#6E7455',
          deep: '#4F553A',
        },
        ochre: {
          DEFAULT: '#D9A863',
          deep: '#A8763F',
        },
        plum: '#8A6B7C',
        'teal-deep': '#4E7A6E',
      },
      fontFamily: {
        // Montserrat carries the whole interface; Caveat is the cursive accent used
        // for annotations and eyebrow labels; JetBrains Mono is reserved for data.
        // 'serif' stays as a display alias so older font-serif classes keep working.
        sans: ['Montserrat', 'system-ui', 'sans-serif'],
        display: ['Montserrat', 'system-ui', 'sans-serif'],
        serif: ['Montserrat', 'system-ui', 'sans-serif'],
        hand: ['Caveat', 'cursive'],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'monospace'],
      },
      boxShadow: {
        // Light glass needs a soft warm drop plus a bright inner top edge; a neutral
        // grey shadow on a beige ground reads as dirt.
        glass: '0 1px 0 0 rgba(255,255,255,0.85) inset, 0 14px 34px -16px rgba(42,39,35,0.30)',
        card: '0 1px 0 0 rgba(255,255,255,0.75) inset, 0 8px 20px -12px rgba(42,39,35,0.28)',
        lift: '0 18px 40px -18px rgba(42,39,35,0.38)',
      },
      keyframes: {
        'sheen-sweep': {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(320%)' },
        },
      },
      animation: {
        'sheen-sweep': 'sheen-sweep 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
