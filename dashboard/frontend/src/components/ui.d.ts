/* SPDX-License-Identifier: AGPL-3.0-or-later */
import type { CSSProperties, ReactNode, Key } from 'react'

// All components accept React's special `key` prop implicitly —
// we declare it explicitly here to satisfy TS when key is passed at call sites.

interface WithKey { key?: Key }

export declare function StatusDot(props: WithKey & { status: string; size?: number }): JSX.Element

export declare function Badge(props: WithKey & { children?: ReactNode; color?: string }): JSX.Element

export declare function Card(props: WithKey & {
  children?: ReactNode
  style?: CSSProperties
  className?: string
  onClick?: () => void
  [key: string]: any
}): JSX.Element

export declare function SectionLabel(props: WithKey & { children?: ReactNode }): JSX.Element

export declare function PageHeader(props: WithKey & {
  eyebrow?: string
  title?: ReactNode
  description?: ReactNode
  meta?: ReactNode
  actions?: ReactNode
}): JSX.Element

export declare function PanelHeader(props: WithKey & {
  eyebrow?: string
  title?: ReactNode
  description?: ReactNode
  aside?: ReactNode
}): JSX.Element

export declare function StatCard(props: WithKey & {
  label: string
  value?: ReactNode
  unit?: string
  color?: string
}): JSX.Element

export declare function Empty(props: WithKey & { children?: ReactNode }): JSX.Element

export declare function Skeleton(props: WithKey & {
  width?: string | number
  height?: number
  radius?: number
  style?: CSSProperties
  className?: string
}): JSX.Element

export declare function SkeletonText(props: WithKey & { lines?: number }): JSX.Element

export declare function LoadingPanel(props: WithKey & {
  eyebrow?: string
  title?: string
  body?: string
}): JSX.Element

export declare function Ts(props: WithKey & { value?: string | number | null }): JSX.Element | null

export declare function Btn(props: WithKey & {
  children?: ReactNode
  onClick?: () => void
  variant?: string
  size?: string
  disabled?: boolean
}): JSX.Element

export declare function Row(props: WithKey & {
  left?: ReactNode
  center?: ReactNode
  right?: ReactNode
  onClick?: () => void
  chevron?: boolean
}): JSX.Element

export declare function ShortcutKey(props: WithKey & { children?: ReactNode }): JSX.Element
