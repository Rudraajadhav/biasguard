/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          900: '#0a0c10',   // deepest background
          800: '#0f1218',   // panel background
          700: '#161a22',   // raised surface
          600: '#1f2530',   // border / hover
          500: '#2b323f',   // muted border
        },
        mint: {
          DEFAULT: '#5eead4',  // primary accent — calm, disciplined
          dim: '#3aa893',
          glow: '#5eead433',
        },
        amber: {
          DEFAULT: '#e0a740',  // warning — FOMO / caution
          dim: '#a87d2f',
        },
        coral: {
          DEFAULT: '#e8654f',  // alert — panic
          dim: '#a8473a',
        },
        fog: {
          100: '#e6e9ef',   // brightest text
          300: '#a7afbe',   // secondary text
          500: '#6b7280',   // muted text
        },
      },
      fontFamily: {
        display: ['Fraunces', 'serif'],
        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 40px -10px rgba(94, 234, 212, 0.25)',
        panel: '0 8px 40px -12px rgba(0, 0, 0, 0.6)',
      },
      backgroundImage: {
        'grid-faint':
          'linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)',
      },
    },
  },
  plugins: [],
}
