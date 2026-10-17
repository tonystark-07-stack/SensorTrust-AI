/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        qn: {
          bg: '#F8F8F6',
          surface: '#FFFFFF',
          subtle: '#F1F1EF',
          border: '#D8D8D5',
          'border-light': '#EBEBEA',
          charcoal: '#242424',
          dark: '#181818',
          text: '#242424',
          muted: '#666666',
          dim: '#8E8E8A',
          green: '#39E75F',
          'green-dark': '#10B981',
          'green-light': '#EDFDF2',
          amber: '#D97706',
          'amber-light': '#FEF3C7',
          red: '#DC2626',
          'red-light': '#FEE2E2',
          blue: '#2563EB',
          'blue-light': '#EFF6FF',
          purple: '#7C3AED',
          'purple-light': '#F5F3FF',
        },
        // Keep grimoire mapping for any legacy classes without glowing effects
        grimoire: {
          bg: '#F8F8F6',
          surface: '#FFFFFF',
          card: '#FFFFFF',
          border: '#D8D8D5',
          accent: '#242424',
          'accent-light': '#39E75F',
          danger: '#DC2626',
          warning: '#D97706',
          success: '#10B981',
          info: '#2563EB',
          muted: '#666666',
          text: '#242424',
          'text-dim': '#666666',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        'qn-card': '0 1px 3px rgba(0,0,0,0.03), 0 1px 2px rgba(0,0,0,0.02)',
        'qn-hover': '0 4px 12px rgba(0,0,0,0.05)',
        'qn-active': '0 0 0 2px #39E75F',
      },
      borderRadius: {
        'qn': '4px',
        'qn-sm': '2px',
        'qn-md': '6px',
      },
    },
  },
  plugins: [],
}
