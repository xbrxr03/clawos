/* SPDX-License-Identifier: AGPL-3.0-or-later */
import type {
  OpenClawImportManifest,
  ProviderProfile,
  SetupDiagnostics,
  SetupState,
  UseCasePack,
} from '../../lib/commandCenterApi'

export type StepId =
  | 'welcome'
  | 'hardware'
  | 'profile'
  | 'runtimes'
  | 'framework'
  | 'model'
  | 'voice'
  | 'policy'
  | 'summary'

export type Busy = string | null

export interface ScreenProps {
  state: SetupState
  diagnostics: SetupDiagnostics | null
  packs: UseCasePack[]
  providers: ProviderProfile[]
  importManifest: OpenClawImportManifest | null
  busy: Busy
  error: string

  /** local UI flags — persisted in localStorage, not backend */
  ui: WizardUI
  setUi: (patch: Partial<WizardUI>) => void

  /** stepper */
  stepIndex: number
  totalSteps: number
  onBack: (() => void) | null
  onNext: () => void
  onSkip?: () => void

  /** API actions (all return the fresh SetupState or null on error) */
  inspect: () => Promise<void>
  updateOptions: (body: Record<string, unknown>) => Promise<void>
  updatePresence: (body: Record<string, unknown>) => Promise<void>
  updateAutonomy: (body: Record<string, unknown>) => Promise<void>
  selectPack: (packId: string, secondary?: string[]) => Promise<void>
  selectProvider: (providerId: string) => Promise<void>
  importOpenClaw: () => Promise<void>
  prepareModel: () => Promise<void>
  runVoiceTest: () => Promise<void>
  planSetup: () => Promise<void>
  applySetup: () => Promise<void>
}

export interface WizardUI {
  /** persona from profile screen — influences pack pre-selection */
  user_profile: string
  /** whether hardware rescan has completed at least once */
  hardware_done: boolean
  /** whether the voice end-to-end test has completed */
  voice_tested: boolean
  /** whether the user clicked "bring online" on the summary screen */
  launch_requested: boolean
  /** assistant display name (collected by voice screen — 1d) */
  assistant_name: string
}

export const DEFAULT_UI: WizardUI = {
  user_profile: '',
  hardware_done: false,
  voice_tested: false,
  launch_requested: false,
  assistant_name: '',
}
