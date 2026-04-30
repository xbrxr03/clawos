/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { Choice, Footer, Readout } from '../atoms'
import type { ScreenProps } from '../types'
import { PROFILE_PERSONAS } from './ProfileScreen'

type Runtime = { id: string; title: string; sub: string; tag?: string; sizeGB: number }

const RUNTIMES: Runtime[] = [
  {
    id: 'nexus',
    title: 'Nexus',
    sub: 'Native Ollama function-calling agent. Local, offline, no API keys.',
    tag: 'RECOMMENDED',
    sizeGB: 1.2,
  },
  {
    id: 'picoclaw',
    title: 'PicoClaw',
    sub: 'Lightweight worker. Zero-cost agentic tasks.',
    tag: 'ARM READY',
    sizeGB: 0.6,
  },
  {
    id: 'openclaw',
    title: 'OpenClaw',
    sub: 'Full ecosystem with skills library and MCP support.',
    sizeGB: 2.4,
  },
]

export function RuntimesScreen(props: ScreenProps) {
  const { state, packs, personas, onBack, onNext, stepIndex, totalSteps, updateOptions, selectPack, ui, busy } =
    props
  const selected = state.selected_runtimes?.length ? state.selected_runtimes : ['nexus', 'picoclaw']

  const toggle = async (id: string) => {
    const next = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]
    const enable_openclaw = next.includes('openclaw')
    await updateOptions({ selected_runtimes: next, enable_openclaw })
  }

  // Recommend a primary pack based on persona (from profile screen)
  const personaCatalog = personas.length ? personas : PROFILE_PERSONAS
  const persona = personaCatalog.find((p) => p.id === (state.selected_persona || ui.user_profile))
  const suggestedPackId = persona?.suggested_pack || state.primary_pack || 'daily-briefing-os'
  const suggestedPack = packs.find((p) => p.id === suggestedPackId)
  const currentPackId = state.primary_pack || suggestedPackId

  const disk = selected.reduce((acc, id) => {
    const r = RUNTIMES.find((rt) => rt.id === id)
    return acc + (r?.sizeGB || 0)
  }, 4.7) // base for shared runtime + dashd

  const applyPack = async (packId: string) => {
    await selectPack(packId, state.secondary_packs || [])
  }

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">04 · Runtimes</div>
        <h1 className="wiz-title">Choose your agent runtimes.</h1>
        <p className="wiz-subtitle">
          All three can live side by side. One shared model backend, any framework on top. Pick
          more than one — they route through the same LiteLLM proxy.
        </p>

        <div className="choices" style={{ marginTop: 28 }}>
          {RUNTIMES.map((r) => (
            <Choice
              key={r.id}
              selected={selected.includes(r.id)}
              glyph={r.id === 'nexus' ? '◐' : r.id === 'picoclaw' ? '◓' : '◉'}
              title={r.title}
              sub={r.sub}
              tag={r.tag}
              multi
              disabled={busy === 'options'}
              onClick={() => toggle(r.id)}
            />
          ))}
        </div>

        <div className="panel" style={{ marginTop: 18, padding: 16 }}>
          <Readout
            rows={[
              {
                k: 'selected',
                v: selected.length === 0 ? 'none' : selected.join(' + '),
                tone: 'accent',
              },
              { k: 'backend', v: 'LiteLLM · Ollama' },
              { k: 'disk footprint', v: `≈ ${disk.toFixed(1)} GB` },
            ]}
          />
        </div>

        {/* Primary pack selection — collapses old "packs" step into here */}
        {packs.length > 0 && (
          <div style={{ marginTop: 22 }}>
            <div
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 10,
                color: 'var(--ink-3)',
                letterSpacing: '0.15em',
                marginBottom: 12,
              }}
            >
              PRIMARY PACK
              {persona ? (
                <span style={{ marginLeft: 10, color: 'var(--accent-text)', textTransform: 'none', letterSpacing: 0 }}>
                  suggested for {persona.title}
                </span>
              ) : null}
            </div>
            <div className="choices cols-2">
              {packs.slice(0, 4).map((pack) => (
                <Choice
                  key={pack.id}
                  selected={currentPackId === pack.id}
                  glyph={pack.id === suggestedPackId ? '★' : '◇'}
                  title={pack.name}
                  sub={pack.setup_summary || pack.description}
                  tag={pack.id === suggestedPackId ? 'RECOMMENDED' : undefined}
                  disabled={busy === 'pack'}
                  onClick={() => applyPack(pack.id)}
                />
              ))}
            </div>
            {suggestedPack && currentPackId !== suggestedPackId ? (
              <div className="hint" style={{ marginTop: 10 }}>
                ⓘ Suggested pack for your profile is <strong>{suggestedPack.name}</strong>.
              </div>
            ) : null}
          </div>
        )}
      </div>
      <Footer
        onBack={onBack}
        onNext={onNext}
        step={stepIndex + 1}
        total={totalSteps}
        nextDisabled={selected.length === 0}
      />
    </>
  )
}
