/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 可以预设一些 IDE 风格的颜色
        'ide-bg': '#1e1e1e',
        'ide-sidebar': '#252526',
        'ide-border': '#333333',
        'primary': '#ff2442',
      },
      boxShadow: {
        'clay': 'inset 0 -8px 12px rgba(0,0,0,0.1), 0 20px 40px rgba(0,0,0,0.15)',
        'paper': '0 4px 10px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)',
      },
      animation: {
        'fade-up': 'fadeUp 0.6s ease-out forwards',
      },
      keyframes: {
        fadeUp: {
          'from': { opacity: '0', transform: 'translateY(20px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        }
      }
    },
  },
  plugins: [],
}
