/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'sans-serif']
      },
      colors: {
        slatebiz: {
          50: '#f4f7fb',
          100: '#e8eef7',
          500: '#5b6e8a',
          700: '#33465f',
          900: '#1d2a3b'
        }
      }
    }
  },
  plugins: []
}
