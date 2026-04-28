/* SPDX-License-Identifier: AGPL-3.0-or-later
 * FrameworkScreen — lets the user opt into an additional agent framework
 * on top of the built-in Nexus loop. Tier-filters the frameworks.registry
 * catalog against the hardware profile_id detected on the HardwareScreen.
 * Single-select with explicit "Built-in only" default — no framework is a
 * valid (and fast) choice.
 */
import { useEffect, useMemo, useState } from 'react'
import { commandCenterApi, type FrameworkCatalogEntry } from '../../../lib/commandCenterApi'
import { Choice, Footer, Readout } from '../atoms'
import type { ScreenProps } from '../types'
import { OpenClawOnboardModal } from './OpenClawOnboardModal'

/** Map catalog names to a short glyph + marketing tag. Anything missing falls
 *  back to a neutral glyph — we never hardcode framework identity here, just
 *  visual chrome. */
const GLYPHS: Record<string, { glyph: string; tag?: string }> = {
  smolagents:     { glyph: '✦', tag: 'POPULAR' },
  openclaw:       { glyph: '◉', tag: 'SKILLS' },
  agentzero:      { glyph: '◐' },
  langroid:       { glyph: '⟲' },
  pocketflow:     { glyph: '◈' },
  openai_agents:  { glyph: '○' },
  nanoclaw:       { glyph: '▱' },
  nullclaw:       { glyph: '◌' },
  zeroclaw:       { glyph: '◇' },
}

const FRIENDLY_NAMES: Record<string, string> = {
  smolagents:    'SmolAgents',
  openclaw:      'OpenClaw',
  agentzero:     'Agent Zero',
  langroid:      'Langroid',
  pocketflow:    'PocketFlow',
  openai_agents: 'OpenAI Agents',
  nanoclaw:      'NanoClaw',
  nullclaw:      'NullClaw',
  zeroclaw:      'ZeroClaw',
}

export function FrameworkScreen(props: ScreenProps) {
  const { state, onBack, onNext, stepIndex, totalSteps, updateOptions, busy } = props
  const [items, setItems] = useState<FrameworkCatalogEntry[] | null>(null)
  const [loadError, setLoadError] = useState('')
  const [showOnboardModal, setShowOnboardModal] = useState(false)

  const profileId = state.detected_hardware?.profile_id || ''
  const selected = state.selected_framework || ''
  const onboarded = !!(state as Record<string, unknown>).openclaw_onboarded

  useEffect(() => {
    let cancelled = false
    commandCenterApi
      .listSetupFrameworks(profileId)
      .then((payload) => {
        if (cancelled) return
        const list = Array.isArray(payload?.frameworks) ? payload.frameworks : []
        setItems(list)
        // Auto-select openclaw as default if nothing is chosen yet and it's compatible
        if (!state.selected_framework) {
          const oc = list.find((f: FrameworkCatalogEntry) => f.name === 'openclaw' && f.compatible)
          if (oc) updateOptions({ selected_framework: 'openclaw' }).catch(() => null)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const msg = err instanceof Error ? err.message : 'Agent catalog unavailable'
        setLoadError(msg)
        setItems([])
      })
    return () => {
      cancelled = true
    }
  }, [profileId]) // eslint-disable-line react-hooks/exhaustive-deps

  const pick = async (id: string) => {
    // Empty string is valid — clears the selection and falls back to built-in only.
    await updateOptions({ selected_framework: id })
  }

  // Sort: compatible first, then alphabetical. Incompatible entries stay visible
  // but disabled, so users on low-RAM tiers see *why* a choice isn't available
  // instead of it just vanishing.
  const ordered = useMemo(() => {
    if (!items) return []
    return [...items].sort((a, b) => {
      if (!!b.compatible !== !!a.compatible) return a.compatible ? -1 : 1
      return (a.name || '').localeCompare(b.name || '')
    })
  }, [items])

  const compatibleCount = useMemo(
    () => ordered.filter((f) => f.compatible).length,
    [ordered],
  )

  const selectedEntry = ordered.find((f) => f.name === selected) || null

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">05 · Agent</div>
        <h1 className="wiz-title">Choose JARVIS's brain.</h1>
        <p className="wiz-subtitle">
          ClawOS wraps any agent framework and gives it voice, memory, and the JARVIS persona.
          OpenClaw is recommended — deepest integration and best skills library.
          You can swap agents later from Settings.
        </p>

        <div className="panel" style={{ marginTop: 24, padding: 16 }}>
          <Readout
            rows={[
              {
                k: 'hardware profile',
                v: profileId || 'unknown',
                tone: 'accent',
              },
              {
                k: 'catalog',
                v: items == null ? 'loading…' : `${compatibleCount} of ${ordered.length} compatible`,
              },
              {
                k: 'agent brain',
                v: selected
                  ? FRIENDLY_NAMES[selected] || selected
                  : 'none selected',
                tone: selected ? 'ok' : 'default',
              },
            ]}
          />
        </div>

        {loadError ? (
          <div className="note err" style={{ marginTop: 16 }}>
            <span>✕</span>
            {loadError}
          </div>
        ) : null}

        <div className="choices cols-2" style={{ marginTop: 22 }}>
          {items == null
            ? null
            : ordered.map((f) => {
                const meta = GLYPHS[f.name] || { glyph: '◆' }
                const title = FRIENDLY_NAMES[f.name] || f.name
                const isOC = f.name === 'openclaw'
                const sub = f.compatible
                  ? f.description || 'Agent framework'
                  : `Incompatible — ${f.incompatible_reason || 'not supported on this tier'}`
                const isInstalled = f.state === 'installed' || f.state === 'running'
                const tag = !f.compatible
                  ? undefined
                  : isInstalled
                    ? 'INSTALLED'
                    : isOC
                      ? 'RECOMMENDED'
                      : meta.tag
                return (
                  <Choice
                    key={f.name}
                    selected={selected === f.name}
                    glyph={meta.glyph}
                    title={title}
                    sub={sub}
                    tag={tag}
                    disabled={!f.compatible || busy === 'options'}
                    onClick={() => f.compatible && pick(f.name)}
                  />
                )
              })}
          {/* Deemphasised skip option at the end */}
          <Choice
            key="__none__"
            selected={!selected}
            glyph="◯"
            title="Configure later"
            sub="No agent now. JARVIS will have limited reasoning until you add one from Settings."
            disabled={busy === 'options'}
            onClick={() => pick('')}
          />
        </div>

        {selectedEntry && selectedEntry.name !== 'openclaw' ? (
          <div className="note" style={{ marginTop: 22 }}>
            <span>↪</span>
            <span>JARVIS will use</span>
            <strong style={{ marginLeft: 4 }}>
              {FRIENDLY_NAMES[selectedEntry.name] || selectedEntry.name}
            </strong>{' '}
            <span style={{ marginLeft: 'auto', color: 'var(--ink-3)' }}>
              as its agent brain · installed at apply step
            </span>
          </div>
        ) : null}

        {selectedEntry?.name === 'openclaw' ? (
          <div className="note" style={{ marginTop: 22 }}>
            <span>◉</span>
            <strong style={{ marginLeft: 4 }}>OpenClaw</strong>
            {onboarded ? (
              <span style={{ marginLeft: 8, color: 'var(--ok)' }}>
                ✓ configured — JARVIS is ready
              </span>
            ) : (
              <span style={{ marginLeft: 8, color: 'var(--ink-3)' }}>
                needs a quick setup — configure model, workspace, and gateway
              </span>
            )}
            {!onboarded && (
              <button
                onClick={() => setShowOnboardModal(true)}
                style={{
                  marginLeft: 'auto',
                  background: 'var(--accent)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 6,
                  padding: '5px 14px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Set Up JARVIS →
              </button>
            )}
          </div>
        ) : null}
      </div>

      {showOnboardModal && (
        <OpenClawOnboardModal
          ramGb={state.detected_hardware?.ram_gb as number | undefined}
          selectedModel={state.selected_models?.[0] || undefined}
          onDone={async () => {
            setShowOnboardModal(false)
            await updateOptions({ selected_framework: 'openclaw', openclaw_onboarded: true })
            onNext()
          }}
          onDismiss={() => setShowOnboardModal(false)}
        />
      )}

      <Footer
        onBack={onBack}
        onNext={selected === 'openclaw' && !onboarded ? () => setShowOnboardModal(true) : onNext}
        step={stepIndex + 1}
        total={totalSteps}
        nextLabel={
          !selected
            ? 'Skip for now'
            : selected === 'openclaw' && !onboarded
              ? 'Set Up JARVIS →'
              : 'Continue'
        }
      />
    </>
  )
}
