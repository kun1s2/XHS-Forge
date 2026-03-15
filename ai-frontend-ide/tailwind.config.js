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
      }
    },
  },
  plugins: [],
}
