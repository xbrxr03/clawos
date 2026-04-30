# Contributing to ClawOS

Thanks for your interest. ClawOS is a local-first AI agent stack — every
contribution should preserve that promise (no cloud, no API keys, no
telemetry, runs offline).

---

## Quick start

```bash
git clone https://github.com/xbrxr03/clawos.git
cd clawos
pip install -e ".[dev]"

# Run the agent unit tests (fast, no live LLM)
pytest tests/unit/test_agent_*.py -q
```

---

## How to contribute

### Bug fixes
- Open an issue first if it's non-trivial — saves time
- Branch from `main`, name like `fix/<short-description>`
- Add a regression test where it makes sense
- Open a PR with the fix + test

### Features
- Open an issue describing the feature first
- Wait for a maintainer to mark it `accepted` before writing code
- Branch like `feat/<short-description>`
- Keep PRs small — split large features into multiple PRs

### Docs
- README, `docs/`, code comments — all welcome
- Run `grep -i "todo\|fixme"` over your changes, clean them up before
  PR

---

## Code style

- **Python:** stdlib + already-pinned dependencies. Don't add heavy deps
  without strong justification.
- **TypeScript / React:** match the surrounding file's style. No
  Tailwind, no shadcn — we use a custom design system in
  `dashboard/frontend/src/`.
- **Comments:** WHY only, never WHAT. The code already explains what.
- **New files:** SPDX-License-Identifier header at top, docstring
  explaining the module's role.
- **Type hints:** encouraged but not enforced. Match the surrounding
  file.

### Where things live

| What | Where |
|------|-------|
| New agent tools | `runtimes/agent/tools/{category}.py` |
| Tool schemas | `runtimes/agent/tool_schemas.py` |
| New daemons | `services/{name}d/` |
| Dashboard pages | `dashboard/frontend/src/pages/{Page}.tsx` |
| Setup wizard screens | `dashboard/frontend/src/pages/setup/screens/` |
| Tests | `tests/unit/test_{module}.py` |

---

## Commit messages

Match the existing style:

```
type(scope): brief description

Longer explanation if needed. WHY this change, not WHAT.

Co-Authored-By: ... (if pairing)
```

Examples:
- `fix(install): handle missing python3 on Debian 12`
- `feat(reminderd): notification daemon for due reminders`
- `refactor(toolbridge): consolidate shell allowlist into single module`

---

## What we won't accept

- **Telemetry of any kind.** Zero. Forever. This is a hard line.
- **Cloud-dependent features** that can't be disabled or run offline
- **Closed-source dependencies** (commercial libraries with restrictive licenses)
- **Anything that breaks the offline-first promise** without an
  explicit user opt-in
- **AI-slop PRs** — code that obviously wasn't read, tests that don't
  test anything, comments narrating each line

---

## Testing

```bash
# Agent loop unit tests (fast, runs in <2s)
pytest tests/unit/test_agent_*.py -q

# Full unit suite
pytest tests/unit -q

# Integration (slower, exercises live services)
pytest tests/integration -q
```

Don't write tests that hit live LLMs — mock them or skip.

---

## License

ClawOS is [AGPL-3.0](LICENSE). By contributing, you agree your code
is licensed under the same terms.

---

## Community

- 🐛 [Issues](https://github.com/xbrxr03/clawos/issues) for bugs
- 💬 GitHub Discussions for questions and ideas
