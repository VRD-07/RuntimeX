import defaultTheme from "tailwindcss/defaultTheme.js";


/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        vintage: {
          cream: '#F1ECE6',
          greige: '#DDD5CD',
          rosewood: '#7D4047',
          espresso: '#2E2E2E',
          base: '#1a1919' // A darker shade of espresso for the main background
        }
      },
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
        display: ['Inter', ...defaultTheme.fontFamily.sans],
        montserrat: ['Montserrat', ...defaultTheme.fontFamily.sans],
        playfair: ['"Playfair Display"', ...defaultTheme.fontFamily.serif],
      }
    },
  },
  plugins: [],
}
