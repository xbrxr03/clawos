/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { Footer, ProgressBar, Readout } from '../atoms'
import type { ScreenProps } from '../types'

/**
 * Three tier models the Nexus runtime's dynamic router uses:
 *   FAST  — short queries, single-tool turns, system control
 *   SMART — multi-step reasoning, content generation, briefings (default)
 *   CODER — file/code/shell tasks, anything where code quality matters
 *
 * Option A (April 2026): pre-select all three by default so the runtime
 * always has its tier models. User can deselect on disk-constrained boxes.
 */
type Tier = 'fast' | 'smart' | 'coder'
type Model = {
  id: string
  tier: Tier
  tierLabel: string
  title: string
  role: string
  size: number      // GB
  defaultOn: boolean
}

const MODELS: Model[] = [
  {
    id: 'qwen2.5:3b',
    tier: 'fast',
    tierLabel: 'FAST',
    title: 'qwen2.5:3b',
    role: 'Sub-2s replies for system control, reminders, app launching, simple queries.',
    size: 1.9,
    defaultOn: true,
  },
  {
    id: 'qwen2.5:7b',
    tier: 'smart',
    tierLabel: 'SMART · DEFAULT',
    title: 'qwen2.5:7b',
    role: 'Multi-step reasoning, briefings, content generation. Best tool-calling accuracy.',
    size: 4.7,
    defaultOn: true,
  },
  {
    id: 'qwen2.5-coder:7b',
    tier: 'coder',
    tierLabel: 'CODER',
    title: 'qwen2.5-coder:7b',
    role: 'File ops, shell commands, code generation, workflows. Auto-routed for code tasks.',
    size: 4.7,
    defaultOn: true,
  },
]

export function ModelScreen(props: ScreenProps) {
  const {
    state,
    onBack,
    onNext,
    stepIndex,
    totalSteps,
    updateOptions,
    prepareModel,
    busy,
  } = props

  // Selection: derive from state.selected_models. Default to all three.
  const selectedSet = new Set(
    state.selected_models?.length
      ? state.selected_models
      : MODELS.filter((m) => m.defaultOn).map((m) => m.id),
  )

  const progress = state.model_pull_progress || {}
  const perModel: Array<{ name: string; percent: number; status: string }> =
    (progress.models as Array<{ name: string; percent: number; status: string }>) || []
  const aggregatePct = Number(progress.percent || 0)
  const ready = aggregatePct >= 100 || state.progress_stage === 'model-ready'
  const pulling = busy === 'model' || (aggregatePct > 0 && aggregatePct < 100)

  const localProvider =
    !state.selected_provider_profile || state.selected_provider_profile === 'local-ollama'

  const totalSelectedGB = MODELS.filter((m) => selectedSet.has(m.id))
    .reduce((sum, m) => sum + m.size, 0)

  const toggle = async (id: string) => {
    const next = new Set(selectedSet)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    // Preserve original ordering (FAST → SMART → CODER) so the
    // backend log + UI list stay readable.
    const ordered = MODELS.filter((m) => next.has(m.id)).map((m) => m.id)
    if (ordered.length === 0) return // refuse empty selection
    await updateOptions({ selected_models: ordered })
  }

  const findStatus = (id: string) => perModel.find((p) => p.name === id)

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">06 · Models</div>
        <h1 className="wiz-title">Pull your local models.</h1>
        <p className="wiz-subtitle">
          Nexus uses three specialized models — a fast one for quick taps, a smart one for
          reasoning, and a coder one for file and shell tasks. The agent routes between them
          automatically. They stay on your machine, no internet required after this step.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.4fr 1fr',
            gap: 22,
            marginTop: 26,
          }}
        >
          {/* LEFT — model cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {MODELS.map((m) => {
              const on = selectedSet.has(m.id)
              const status = findStatus(m.id)
              const pct = status?.percent ?? 0
              const stateLabel = status?.status ?? (on ? 'queued' : 'skipped')
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => !pulling && toggle(m.id)}
                  disabled={pulling}
                  style={{
                    textAlign: 'left',
                    padding: 16,
                    borderRadius: 10,
                    border: `1px solid ${on ? 'var(--accent)' : 'var(--panel-br)'}`,
                    background: on ? 'rgba(255,200,0,0.06)' : 'rgba(255,255,255,0.02)',
                    color: 'inherit',
                    cursor: pulling ? 'default' : 'pointer',
                    opacity: pulling && !on ? 0.4 : 1,
                    transition: 'all 0.15s',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 12,
                      marginBottom: 6,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 10,
                        letterSpacing: '0.18em',
                        color: on ? 'var(--accent)' : 'var(--ink-3)',
                      }}
                    >
                      {m.tierLabel}
                    </span>
                    <span style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.01em' }}>
                      {m.title}
                    </span>
                    <span
                      style={{
                        marginLeft: 'auto',
                        fontFamily: 'var(--mono)',
                        fontSize: 11,
                        color: 'var(--ink-3)',
                      }}
                    >
                      {m.size} GB
                    </span>
                  </div>
                  <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>
                    {m.role}
                  </div>
                  {on && (status || pulling) && (
                    <div style={{ marginTop: 10 }}>
                      <ProgressBar pct={pct} />
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          marginTop: 4,
                          fontFamily: 'var(--mono)',
                          fontSize: 10,
                          color: 'var(--ink-3)',
                        }}
                      >
                        <span>{stateLabel}</span>
                        <span>{pct.toFixed(0)}%</span>
                      </div>
                    </div>
                  )}
                </button>
              )
            })}
          </div>

          {/* RIGHT — totals + pull control */}
          <div className="panel hud" style={{ padding: 22 }}>
            <div
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 10,
                color: 'var(--ink-3)',
                letterSpacing: '0.15em',
                marginBottom: 14,
              }}
            >
              {localProvider ? 'DOWNLOAD' : 'PROVIDER'}
            </div>
            <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em' }}>
              {selectedSet.size} model{selectedSet.size !== 1 ? 's' : ''}
            </div>
            <div
              style={{
                fontSize: 12,
                color: 'var(--ink-3)',
                fontFamily: 'var(--mono)',
                marginTop: 4,
              }}
            >
              {totalSelectedGB.toFixed(1)} GB · Apache-2.0 · Q4_K_M
            </div>

            <div className="hair" style={{ margin: '18px 0' }} />

            <Readout
              rows={[
                {
                  k: 'aggregate',
                  v: pulling
                    ? `${aggregatePct.toFixed(0)}%`
                    : ready
                      ? 'all ready'
                      : localProvider
                        ? 'idle'
                        : 'remote',
                  tone: ready ? 'ok' : 'default',
                },
                {
                  k: 'eta',
                  v:
                    pulling && Number(progress.eta_seconds || 0) > 0
                      ? `${progress.eta_seconds}s`
                      : ready
                        ? 'verified'
                        : localProvider
                          ? `est ${Math.round(totalSelectedGB / 0.035)}s`
                          : '—',
                },
                {
                  k: 'endpoint',
                  v: localProvider ? 'ollama:11434' : 'remote',
                },
              ]}
            />

            <div className="hair" style={{ margin: '18px 0' }} />

            {localProvider && !pulling && !ready && (
              <button
                type="button"
                className="wiz-btn wiz-btn-primary"
                onClick={prepareModel}
                style={{ width: '100%', justifyContent: 'center' }}
                disabled={selectedSet.size === 0}
              >
                ⤓ Pull {selectedSet.size} model{selectedSet.size !== 1 ? 's' : ''}
                {' '}({totalSelectedGB.toFixed(1)} GB)
              </button>
            )}
            {localProvider && pulling && (
              <div className="hint" style={{ textAlign: 'center' }}>
                <span className="blink">▍</span>
                {' '}{progress.status || `pulling ${progress.model || '…'}`}
              </div>
            )}
            {(ready || !localProvider) && (
              <div
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                  color: 'var(--ok)',
                  textAlign: 'center',
                }}
              >
                ✓ models ready · agent loop routes between them
              </div>
            )}

            {!ready && !pulling && totalSelectedGB > 8 && (
              <div
                className="hint"
                style={{
                  marginTop: 12,
                  fontSize: 11,
                  color: 'var(--ink-3)',
                  textAlign: 'center',
                }}
              >
                first pull on this connection — grab a coffee
              </div>
            )}
          </div>
        </div>
      </div>

      <Footer
        onBack={onBack}
        onNext={onNext}
        step={stepIndex + 1}
        total={totalSteps}
        nextDisabled={localProvider && !ready}
        nextLabel={localProvider && !ready ? 'Pull models first' : 'Continue'}
      />
    </>
  )
}
