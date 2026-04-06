# Competitive Platform

ClawOS is no longer just a local installer for OpenClaw. The product direction is now:

- OpenClaw-first migration
- local-first execution
- provider-neutral internals
- no paid product tier
- premium command-center UX

This document tracks the concrete primitives and surfaces that support that position.

## Product Surfaces

- `ClawOS Setup`
  - pack-first onboarding
  - provider profile selection
  - OpenClaw rescue/import
  - extension recommendations
- `ClawOS Command Center`
  - packs
  - providers
  - registry
  - traces
  - workflows
  - approvals
  - models
  - diagnostics
- `ClawOS Web Access`
  - browser-served version of the same product frontend

## Core Primitives

- `UseCasePack`
  - packaged outcome
  - setup defaults
  - dashboards
  - workflows
  - provider recommendations
  - policy defaults
  - eval suite
- `ProviderProfile`
  - local and cloud provider definitions
  - auth posture
  - default models
  - fallback order
  - cost and privacy labels
- `ExtensionManifest`
  - typed extension metadata
  - trust tier
  - permissions
  - network posture
  - pack dependencies
- `WorkflowProgram`
  - declarative workflow definition for long-term pack orchestration
- `TraceRecord`
  - local run record for packs, providers, setup, and extension activity
- `OpenClawImportManifest`
  - detected OpenClaw install
  - channels
  - skills
  - providers
  - migration actions
  - blockers and warnings

## Wave 1 Packs

- `daily-briefing-os`
- `sales-meeting-operator`
- `chat-app-command-center`
- `coding-autopilot`

These are the first packs ClawOS should make production-grade. Each one needs:

- a setup path
- seeded dashboards
- default workflows
- recommended extensions
- provider recommendations
- a policy pack
- an eval suite

## Provider Control Plane

The default provider posture is:

- `local-ollama` first
- explicit cloud profiles only when requested
- no provider credential leakage into agent context
- visible privacy and cost labels
- fallback routing instead of hard vendor dependence

Current profile targets:

- `local-ollama`
- `anthropic-api`
- `openai-api`
- `azure-openai`
- `openai-compatible`
- `openrouter`

## Registry and Trust Model

The registry must remain explicit about trust. Extensions should always surface:

- trust tier
- permission list
- network posture
- category
- pack fit

ClawOS uses three lanes:

- `Verified`
- `Community`
- `Quarantined`

## OpenClaw Rescue

ClawOS should be the easiest way to leave a fragile OpenClaw setup without losing the reason you installed it.

The rescue path should:

- inspect an existing OpenClaw home
- detect channels, providers, and skills
- summarize environment dependence
- recommend a primary ClawOS pack
- import safe configuration
- switch to a more stable provider posture when needed

## Current API Surface

Setup:

- `POST /api/setup/inspect`
- `POST /api/setup/select-pack`
- `POST /api/setup/import/openclaw`

Command Center:

- `GET /api/packs`
- `POST /api/packs/install`
- `GET /api/providers`
- `POST /api/providers/test`
- `POST /api/providers/switch`
- `GET /api/extensions`
- `POST /api/extensions/install`
- `GET /api/traces`
- `GET /api/evals`
- `GET /api/a2a/agent-card`
- `POST /api/a2a/tasks`

## Current CLI Surface

- `clawctl packs list`
- `clawctl packs install <pack-id>`
- `clawctl providers list`
- `clawctl providers test <profile-id>`
- `clawctl providers switch <profile-id>`
- `clawctl extensions list`
- `clawctl extensions install <extension-id>`
- `clawctl rescue openclaw`
- `clawctl benchmark`

## What Comes Next

The next layers that complete the competitive moat are:

- Browser Workbench
- local research engine with citations and resumable runs
- MCP manager
- richer A2A federation and peer trust
- OTEL-native trace export
- Pack Studio visual builder
- stronger signed extension packaging and rollback support
