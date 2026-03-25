/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
      },
      colors: {
        claw: {
          bg:      '#0a0c10',
          surface: '#111418',
          border:  '#1e2330',
          muted:   '#2a3040',
          accent:  '#00e5a0',
          warn:    '#f59e0b',
          danger:  '#ef4444',
          info:    '#3b82f6',
          text:    '#e2e8f0',
          dim:     '#64748b',
        },
      },
    },
  },
  plugins: [],
}
