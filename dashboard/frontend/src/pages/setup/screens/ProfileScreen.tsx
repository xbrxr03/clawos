/* SPDX-License-Identifier: AGPL-3.0-or-later */
import type { SetupPersona } from '../../../lib/commandCenterApi'
import { Choice, Footer } from '../atoms'
import type { ScreenProps } from '../types'

const PROFILES: SetupPersona[] = [
  {
    id: 'developer',
    glyph: '{ }',
    title: 'Developer',
    subtitle: 'Coding, git, repos, code review. OpenClaw + qwen2.5-coder.',
    tag: 'POPULAR',
    goals: ['code review', 'git workflows', 'repo analysis'],
    suggested_pack: 'coding-autopilot',
  },
  {
    id: 'creator',
    glyph: 'TXT',
    title: 'Content Creator',
    subtitle: 'Writing, captions, images, daily digest workflows.',
    goals: ['daily digest', 'captions', 'long-form drafts'],
    suggested_pack: 'daily-briefing-os',
  },
  {
    id: 'researcher',
    glyph: 'R&D',
    title: 'Researcher',
    subtitle: 'PDFs, note summarisation, knowledge graph.',
    goals: ['paper summarisation', 'knowledge graph', 'citation search'],
    suggested_pack: 'daily-briefing-os',
  },
  {
    id: 'business',
    glyph: 'BIZ',
    title: 'Business',
    subtitle: 'Reports, spreadsheets, lead research, scheduling.',
    goals: ['daily briefing', 'meeting prep', 'lead research'],
    suggested_pack: 'daily-briefing-os',
  },
  {
    id: 'student',
    glyph: 'STU',
    title: 'Student',
    subtitle: 'Lecture notes, wiki, proofread, study plans.',
    goals: ['lecture notes', 'proofreading', 'study plans'],
    suggested_pack: 'daily-briefing-os',
  },
  {
    id: 'teacher',
    glyph: 'EDU',
    title: 'Teacher',
    subtitle: 'Lesson planning, curriculum, scheduling.',
    goals: ['lesson planning', 'curriculum', 'scheduling'],
    suggested_pack: 'daily-briefing-os',
  },
  {
    id: 'freelancer',
    glyph: 'FL',
    title: 'Freelancer',
    subtitle: 'Proposals, client research, outreach, invoicing.',
    goals: ['proposals', 'outreach', 'invoicing'],
    suggested_pack: 'chat-app-command-center',
  },
  {
    id: 'general',
    glyph: 'GEN',
    title: 'General',
    subtitle: 'Balanced - a bit of everything.',
    goals: ['daily briefing', 'meeting prep', 'inbox triage'],
    suggested_pack: 'daily-briefing-os',
  },
]

export function ProfileScreen(props: ScreenProps) {
  const { ui, setUi, state, personas, onBack, onNext, stepIndex, totalSteps, updateOptions, selectPack } =
    props
  const catalog = personas.length ? personas : PROFILES
  const picked = state.selected_persona || ui.user_profile

  const pick = async (persona: SetupPersona) => {
    setUi({ user_profile: persona.id })
    try {
      await updateOptions({
        selected_persona: persona.id,
        primary_goals: persona.goals || [],
      })
      if (persona.suggested_pack) {
        await selectPack(persona.suggested_pack, state.secondary_packs || [])
      }
    } catch {
      /* non-fatal - UI state persists in localStorage regardless */
    }
  }

  return (
    <>
      <div className="stage-inner">
        <div className="eyebrow">03 · Profile</div>
        <h1 className="wiz-title">Who is ClawOS for?</h1>
        <p className="wiz-subtitle">
          I&rsquo;ll pre-load the right workflows, skills and model routing for how you actually
          work. You can change this any time from Settings → Profile.
        </p>

        <div className="choices cols-2" style={{ marginTop: 28 }}>
          {catalog.map((persona) => (
            <Choice
              key={persona.id}
              selected={picked === persona.id}
              glyph={persona.glyph}
              title={persona.title}
              sub={persona.subtitle}
              tag={persona.tag}
              onClick={() => pick(persona)}
            />
          ))}
        </div>

        {picked && (
          <div className="note" style={{ marginTop: 22 }}>
            <span>↪</span>
            Profile:{' '}
            <strong style={{ marginLeft: 4 }}>
              {catalog.find((persona) => persona.id === picked)?.title}
            </strong>
            <span style={{ marginLeft: 'auto', color: 'var(--ink-3)' }}>
              workflows pre-selected · model routing tuned
            </span>
          </div>
        )}
      </div>
      <Footer
        onBack={onBack}
        onNext={onNext}
        step={stepIndex + 1}
        total={totalSteps}
        nextDisabled={!picked}
      />
    </>
  )
}

export { PROFILES as PROFILE_PERSONAS }
