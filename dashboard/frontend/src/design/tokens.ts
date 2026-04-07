/* SPDX-License-Identifier: AGPL-3.0-or-later */
export const themes = ['dark', 'light'] as const

export type ThemeName = (typeof themes)[number]

export const designTokens = {
  font: {
    sans: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    display: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif',
    mono: '"SF Mono", "JetBrains Mono", ui-monospace, monospace',
  },
  radius: {
    sm: 6,
    md: 10,
    lg: 14,
    xl: 20,
  },
  layout: {
    sidebar: 200,
    toolbar: 52,
    inspector: 320,
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    xxl: 24,
  },
  colors: {
    dark: {
      background: '#1C1C1E',
      panel: 'rgba(44, 44, 46, 0.82)',
      surface: 'rgba(58, 58, 60, 0.72)',
      accent: '#007AFF',
      accentSecondary: '#5AC8FA',
      success: '#34C759',
      warning: '#FF9500',
      danger: '#FF3B30',
    },
    light: {
      background: '#F2F2F7',
      panel: 'rgba(255, 255, 255, 0.85)',
      surface: 'rgba(242, 242, 247, 0.90)',
      accent: '#007AFF',
      accentSecondary: '#5AC8FA',
      success: '#34C759',
      warning: '#FF9500',
      danger: '#FF3B30',
    },
  },
} as const
