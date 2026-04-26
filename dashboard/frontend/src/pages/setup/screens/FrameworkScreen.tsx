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

  useEffect(() => {
    let cancelled = false
    commandCenterApi
      .listSetupFrameworks(profileId)
      .then((payload) => {
        if (cancelled) return
        setItems(Array.isArray(payload?.frameworks) ? payload.frameworks : [])
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const msg = err instanceof Error ? err.message : 'Framework catalog unavailable'
        setLoadError(msg)
        setItems([])
      })
    return () => {
      cancelled = true
    }
  }, [profileId])

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
        <div className="eyebrow">05 · Framework</div>
        <h1 className="wiz-title">Pick an agent framework.</h1>
        <p className="wiz-subtitle">
          Nexus is always on — this adds a second agent brain for tasks that need
          a different pattern. Tier-filtered against your detected hardware.
          Skip this step and you can install any framework later from Settings → Frameworks.
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
                k: 'current choice',
                v: selected
                  ? FRIENDLY_NAMES[selected] || selected
                  : 'none (built-in Nexus only)',
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
          {/* Always-available "built-in only" option pinned to the top */}
          <Choice
            key="__none__"
            selected={!selected}
            glyph="◯"
            title="Built-in only"
            sub="Just Nexus. Fastest boot, zero extra install. Recommended if you're unsure."
            tag={!selected ? 'DEFAULT' : undefined}
            disabled={busy === 'options'}
            onClick={() => pick('')}
          />
          {items == null
            ? null
            : ordered.map((f) => {
                const meta = GLYPHS[f.name] || { glyph: '◆' }
                const title = FRIENDLY_NAMES[f.name] || f.name
                const sub = f.compatible
                  ? f.description || 'Agent framework'
                  : `Incompatible — ${f.incompatible_reason || 'not supported on this tier'}`
                const isInstalled = f.state === 'installed' || f.state === 'running'
                const tag = !f.compatible
                  ? undefined
                  : isInstalled
                    ? 'INSTALLED'
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
        </div>

        {selectedEntry && selectedEntry.name !== 'openclaw' ? (
          <div className="note" style={{ marginTop: 22 }}>
            <span>↪</span>
            Installing{' '}
            <strong style={{ marginLeft: 4 }}>
              {FRIENDLY_NAMES[selectedEntry.name] || selectedEntry.name}
            </strong>{' '}
            <span style={{ marginLeft: 'auto', color: 'var(--ink-3)' }}>
              queued for the apply step · you can remove it later
            </span>
          </div>
        ) : null}

        {selectedEntry?.name === 'openclaw' ? (
          <div className="note" style={{ marginTop: 22 }}>
            <span>◉</span>
            <strong style={{ marginLeft: 4 }}>OpenClaw</strong>
            <span style={{ marginLeft: 8, color: 'var(--ink-3)' }}>
              requires guided setup — click "Install &amp; Set Up" to continue
            </span>
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
              Install &amp; Set Up →
            </button>
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
        onNext={onNext}
        step={stepIndex + 1}
        total={totalSteps}
        nextLabel={selected && selected !== 'openclaw' ? 'Continue' : 'Skip'}
      />
    </>
  )
}
