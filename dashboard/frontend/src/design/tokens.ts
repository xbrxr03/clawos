/* SPDX-License-Identifier: AGPL-3.0-or-later */
export const themes = ['dark', 'light'] as const

export type ThemeName = (typeof themes)[number]

export const designTokens = {
  font: {
    sans: '"Manrope", "Segoe UI Variable", sans-serif',
    display: '"Sora", "Manrope", sans-serif',
    mono: '"IBM Plex Mono", "SF Mono", ui-monospace, monospace',
  },
  radius: {
    sm: 12,
    md: 18,
    lg: 28,
    xl: 36,
  },
  layout: {
    sidebar: 320,
    toolbar: 76,
    inspector: 336,
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
    xxl: 32,
  },
  colors: {
    dark: {
      background: '#08101a',
      panel: '#111b2b',
      surface: '#182334',
      accent: '#59a6ff',
      accentSecondary: '#5ed9d1',
      success: '#43cb91',
      warning: '#f9bc62',
      danger: '#ff6d76',
    },
    light: {
      background: '#ecf2fa',
      panel: '#ffffff',
      surface: '#f8fafe',
      accent: '#59a6ff',
      accentSecondary: '#5ed9d1',
      success: '#43cb91',
      warning: '#f9bc62',
      danger: '#ff6d76',
    },
  },
} as const
