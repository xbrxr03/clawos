export const themes = ['dark', 'light'] as const

export type ThemeName = (typeof themes)[number]

export const designTokens = {
  font: {
    sans: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    mono: '"JetBrains Mono", "SF Mono", ui-monospace, monospace',
  },
  radius: {
    sm: 10,
    md: 16,
    lg: 24,
  },
  layout: {
    sidebar: 280,
    toolbar: 68,
    inspector: 320,
  },
  colors: {
    dark: {
      background: '#0b1018',
      panel: '#121a28',
      accent: '#4d8ff7',
      success: '#33c78a',
      warning: '#ffb74d',
      danger: '#ff6b6b',
    },
    light: {
      background: '#eef3fb',
      panel: '#ffffff',
      accent: '#4d8ff7',
      success: '#33c78a',
      warning: '#ffb74d',
      danger: '#ff6b6b',
    },
  },
} as const
