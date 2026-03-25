/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ios: {
          bg:     '#000000',
          bg2:    '#1c1c1e',
          bg3:    '#2c2c2e',
          bg4:    '#3a3a3c',
          blue:   '#0a84ff',
          green:  '#30d158',
          red:    '#ff453a',
          orange: '#ff9f0a',
          yellow: '#ffd60a',
          purple: '#bf5af2',
          teal:   '#40c8e0',
          text:   '#ffffff',
          text2:  'rgba(255,255,255,0.6)',
          text3:  'rgba(255,255,255,0.3)',
          sep:    'rgba(255,255,255,0.08)',
        },
      },
      borderRadius: {
        ios: '16px',
        'ios-sm': '10px',
        'ios-lg': '20px',
      },
      fontFamily: {
        ios: ['-apple-system', 'SF Pro Display', 'SF Pro Text', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
