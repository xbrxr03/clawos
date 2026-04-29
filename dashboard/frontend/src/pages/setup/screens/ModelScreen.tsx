/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { Choice, Footer, ProgressBar, Readout } from '../atoms'
import type { ScreenProps } from '../types'

type Model = { id: string; title: string; sub: string; size: number; tag?: string }

const MODELS: Model[] = [
  {
    id: 'qwen2.5:3b',
    title: 'qwen2.5:3b',
    sub: 'Fastest on CPU · 8 GB RAM, no GPU needed.',
    size: 1.9,
  },
  {
    id: 'qwen2.5:7b',
    title: 'qwen2.5:7b',
    sub: 'Stronger reasoning · 16 GB RAM recommended.',
    size: 4.7,
    tag: 'BEST FIT',
  },
  {
    id: 'qwen2.5-coder:7b',
    title: 'qwen2.5-coder:7b',
    sub: 'Sharper for coding-heavy workflows.',
    size: 4.7,
  },
  {
    id: 'qwen2.5:14b',
    title: 'qwen2.5:14b',
    sub: 'Full agentic use · 32 GB+ target.',
    size: 9.1,
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

  const picked = state.selected_models?.[0] || 'qwen2.5:7b'
  const m = MODELS.find((x) => x.id === picked) || MODELS[1]
  const progress = state.model_pull_progress || {}
  const pct = Number(progress.percent || 0)
  const ready = pct >= 100 || state.progress_stage === 'model-ready'
  const pulling = busy === 'model' || (pct > 0 && pct < 100)

  // Non-local provider → skip pull
  const localProvider =
    !state.selected_provider_profile || state.selected_provider_profile === 'local-ollama'

  const pickModel = async (id: string) => {
    if (id !== picked) await updateOptions({ selected_models: [id] })
  }

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">06 · Model</div>
        <h1 className="wiz-title">Choose your local model.</h1>
        <p className="wiz-subtitle">
          The Ollama model your agent runs on. Stays on your machine, no internet required.
          Swap any time with{' '}
          <span style={{ fontFamily: 'var(--mono)', color: 'var(--ink-1)' }}>
            clawctl model set
          </span>
          .
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.3fr 1fr',
            gap: 20,
            marginTop: 28,
          }}
        >
          <div className="choices">
            {MODELS.map((option) => (
              <Choice
                key={option.id}
                selected={picked === option.id}
                glyph={<span style={{ fontSize: 10 }}>{option.size}GB</span>}
                title={option.title}
                sub={option.sub}
                tag={option.tag}
                disabled={pulling}
                onClick={() => pickModel(option.id)}
              />
            ))}
          </div>

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
            <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em' }}>{m.id}</div>
            <div
              style={{
                fontSize: 12,
                color: 'var(--ink-3)',
                fontFamily: 'var(--mono)',
                marginTop: 2,
              }}
            >
              {m.size} GB · Q4_K_M · Apache-2.0
            </div>

            <div style={{ marginTop: 22 }}>
              <ProgressBar pct={localProvider ? pct : 100} />
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginTop: 8,
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                  color: 'var(--ink-2)',
                }}
              >
                <span>{localProvider ? `${pct.toFixed(0)}%` : 'remote'}</span>
                <span>
                  {pulling
                    ? (progress.status as string) || 'pulling…'
                    : ready
                      ? 'complete'
                      : localProvider
                        ? 'idle'
                        : 'ready'}
                </span>
                <span>
                  {pulling && Number(progress.eta_seconds || 0) > 0
                    ? `eta ${progress.eta_seconds}s`
                    : ready
                      ? 'verified'
                      : localProvider
                        ? `est ${Math.round(m.size / 0.035)}s`
                        : 'provider profile'}
                </span>
              </div>
            </div>

            <div className="hair" />

            {localProvider && !pulling && !ready && (
              <button
                type="button"
                className="wiz-btn wiz-btn-primary"
                onClick={prepareModel}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                ⤓ Pull {m.id}
              </button>
            )}
            {localProvider && pulling && (
              <div className="hint" style={{ textAlign: 'center' }}>
                <span className="blink">▍</span> ollama pull {m.id}…
              </div>
            )}
            {(ready || !localProvider) && (
              <Readout
                rows={[
                  { k: 'status', v: 'ready', tone: 'ok' },
                  {
                    k: 'provider',
                    v: state.selected_provider_profile || 'local-ollama',
                  },
                  { k: 'endpoint', v: localProvider ? 'ollama:11434' : 'remote' },
                ]}
              />
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
        nextLabel={localProvider && !ready ? 'Pull model first' : 'Continue'}
      />
    </>
  )
}
