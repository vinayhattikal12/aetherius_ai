/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#016A71',
          hover: '#01575d',
          active: '#014c51',
          light: '#34888D',
          glow: '#4e99a3',
        },
        accent: {
          DEFAULT: '#34888D',
          light: '#4e99a3',
          dark: '#016A71',
        },
        surface: {
          DEFAULT: '#000000',
          elevated: '#171615',
          card: '#171615',
          hover: '#1e1d1c',
          active: '#242322',
        },
        border: {
          subtle: '#2a2928',
          muted: '#242322',
          active: '#363534',
        },
        text: {
          DEFAULT: '#FFFFFF',
          muted: '#949494',
          secondary: '#d6d5d4',
        },
        brand: {
          50: '#f0f9f9',
          100: '#daf0f1',
          200: '#b8e1e4',
          300: '#8acbd0',
          400: '#4e99a3',
          500: '#34888D',
          600: '#016A71',
          700: '#01575d',
          800: '#01454a',
          900: '#01383c',
          950: '#001f22',
        },
        dark: {
          bg: '#000000',
          surface: '#171615',
          card: '#171615',
          border: '#2a2928',
          hover: '#1e1d1c',
          muted: '#949494',
        }
      },
      borderRadius: {
        '2xs': '2px',
        'xs': '4px',
        'sm': '6px',
        'md': '8px',
        'DEFAULT': '11px',
        'lg': '11px',
        'xl': '12px',
        '2xl': '16px',
        '3xl': '24px',
        'card': '11px',
        'btn': '11px',
      },
      boxShadow: {
        'glow': '0 0 32px 2px rgba(78, 153, 163, 0.25)',
        'glow-sm': '0 0 16px 1px rgba(78, 153, 163, 0.2)',
        'glow-lg': '0 0 48px 4px rgba(78, 153, 163, 0.35)',
        'flat': 'none',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      }
    },
  },
  plugins: [],
}
