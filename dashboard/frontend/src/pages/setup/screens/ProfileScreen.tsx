/* SPDX-License-Identifier: AGPL-3.0-or-later */
import { Choice, Footer } from '../atoms'
import type { ScreenProps } from '../types'

type Persona = {
  id: string
  glyph: string
  title: string
  sub: string
  tag?: string
  goals: string[]
  suggestedPack: string
}

const PROFILES: Persona[] = [
  {
    id: 'developer',
    glyph: '{ }',
    title: 'Developer',
    sub: 'Coding, git, repos, code review. OpenClaw + qwen2.5-coder.',
    tag: 'POPULAR',
    goals: ['code review', 'git workflows', 'repo analysis'],
    suggestedPack: 'coding-autopilot',
  },
  {
    id: 'creator',
    glyph: '✎',
    title: 'Content Creator',
    sub: 'Writing, captions, images, daily digest workflows.',
    goals: ['daily digest', 'captions', 'long-form drafts'],
    suggestedPack: 'daily-briefing-os',
  },
  {
    id: 'researcher',
    glyph: '¶',
    title: 'Researcher',
    sub: 'PDFs, note summarisation, knowledge graph.',
    goals: ['paper summarisation', 'knowledge graph', 'citation search'],
    suggestedPack: 'daily-briefing-os',
  },
  {
    id: 'business',
    glyph: '▤',
    title: 'Business',
    sub: 'Reports, spreadsheets, lead research, scheduling.',
    goals: ['daily briefing', 'meeting prep', 'lead research'],
    suggestedPack: 'daily-briefing-os',
  },
  {
    id: 'student',
    glyph: '∑',
    title: 'Student',
    sub: 'Lecture notes, wiki, proofread, study plans.',
    goals: ['lecture notes', 'proofreading', 'study plans'],
    suggestedPack: 'daily-briefing-os',
  },
  {
    id: 'teacher',
    glyph: '✾',
    title: 'Teacher',
    sub: 'Lesson planning, curriculum, scheduling.',
    goals: ['lesson planning', 'curriculum', 'scheduling'],
    suggestedPack: 'daily-briefing-os',
  },
  {
    id: 'freelancer',
    glyph: '✉',
    title: 'Freelancer',
    sub: 'Proposals, client research, outreach, invoicing.',
    goals: ['proposals', 'outreach', 'invoicing'],
    suggestedPack: 'chat-app-command-center',
  },
  {
    id: 'general',
    glyph: '◈',
    title: 'General',
    sub: 'Balanced — a bit of everything.',
    goals: ['daily briefing', 'meeting prep', 'inbox triage'],
    suggestedPack: 'daily-briefing-os',
  },
]

export function ProfileScreen(props: ScreenProps) {
  const { ui, setUi, onBack, onNext, stepIndex, totalSteps, updateOptions } = props
  const picked = ui.user_profile

  const pick = async (p: Persona) => {
    setUi({ user_profile: p.id })
    // Push persona-derived goals to backend so summary/apply can use them.
    // primary_pack is applied on the runtimes screen.
    try {
      await updateOptions({ primary_goals: p.goals })
    } catch {
      /* non-fatal — UI state persists in localStorage regardless */
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
          {PROFILES.map((p) => (
            <Choice
              key={p.id}
              selected={picked === p.id}
              glyph={p.glyph}
              title={p.title}
              sub={p.sub}
              tag={p.tag}
              onClick={() => pick(p)}
            />
          ))}
        </div>

        {picked && (
          <div className="note" style={{ marginTop: 22 }}>
            <span>↪</span>
            Profile:{' '}
            <strong style={{ marginLeft: 4 }}>
              {PROFILES.find((p) => p.id === picked)?.title}
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
