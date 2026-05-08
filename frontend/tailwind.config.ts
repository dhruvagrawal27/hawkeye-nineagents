import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg:        '#070A18',  // deeper, terminal-grade black
        panel:     '#0B1024',
        panel2:    '#10172E',
        panel3:    '#161E3A',
        muted:     '#1E2748',
        line:      '#1F2A4D',
        ink:       '#E5EAF7',
        dim:       '#7A85AA',
        accent:    '#3B82F6',
        accent2:   '#60A5FA',
        ticker:    '#22D3EE',  // cyan tape accent
        risk: {
          low:      '#10B981',
          medium:   '#F59E0B',
          high:     '#FB923C',
          critical: '#F43F5E',
          flat:     '#64748B',
        },
        flash: {
          up:   '#10B98133',
          down: '#F43F5E33',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['10px', '14px'],
        '3xs': ['9px', '12px'],
      },
      letterSpacing: {
        widest: '0.18em',
      },
      animation: {
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        'tick-up':    'tick-up 800ms ease-out',
        'tick-down':  'tick-down 800ms ease-out',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: '0.55' },
          '50%':      { opacity: '1' },
        },
        'tick-up': {
          '0%':   { backgroundColor: 'rgba(16, 185, 129, 0.4)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'tick-down': {
          '0%':   { backgroundColor: 'rgba(244, 63, 94, 0.4)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
