import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg:        '#0B1020',
        panel:     '#0F172A',
        panel2:    '#111827',
        muted:     '#1E293B',
        accent:    '#3B82F6',
        accent2:   '#60A5FA',
        risk: {
          low:      '#10B981',
          medium:   '#F59E0B',
          high:     '#F97316',
          critical: '#EF4444',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config;
