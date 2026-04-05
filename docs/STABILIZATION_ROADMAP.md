# ClawOS Stabilization Roadmap

## Goal

Make the existing local-agent stack predictable and supportable before adding new surfaces. This roadmap is intentionally narrow: align contracts, reduce duplicate entry points, harden the top workflows, and document the platform boundary clearly.

## Phase 1: Contract Alignment

- Keep `agentd` as the single task entry point.
- Normalize task payloads around `intent`, `workspace`, and `channel`.
- Preserve compatibility for older callers that still send `task`, `source`, or `/tasks`.
- Normalize workflow tool names so older prompts do not break newer runtime contracts.
- Add regression tests around `agentd`, workflow gating, and tool aliases.

Definition of done: all first-party callers use one documented contract, and older callers still work without special-case code in each service.

## Phase 2: Canonical Process Model

- Treat `clients/daemon/daemon.py` plus `services/dashd/api.py` as the canonical boot path.
- Decide whether `dashboard/backend/` stays or is removed.
- Document which modules are true services and which are in-process helpers.
- Add one health endpoint per externally consumed service and wire them into status reporting.

Definition of done: there is one obvious way to boot ClawOS locally and one obvious dashboard stack.

## Phase 3: Workflow Hardening

- Audit the 10 most useful workflows first: repo summary, PR review, README generation, PDF summarization, organize downloads, disk report, log summarize, changelog, duplicate finder, and empty-dir cleanup.
- Replace literal placeholder bugs and outdated tool names.
- Mark Linux-only workflows explicitly instead of silently failing on Windows or macOS.
- Move destructive or multi-step workflows toward small helper functions where prompts alone are too brittle.

Definition of done: the top workflows succeed reliably on supported platforms and fail clearly on unsupported ones.

## Phase 4: Platform Boundary

- Declare the repo Linux-first for install and system services.
- Separate “development on Windows/macOS” from “supported install target”.
- Add graceful fallbacks for non-Linux-only helpers where the cost is low.
- Patch or template systemd units instead of shipping hardcoded home-directory values.

Definition of done: contributors can tell what is supported, what is partially supported, and what is intentionally out of scope.

## Guardrails

- Do not add another dashboard, CLI, or daemon until the current ones are consolidated.
- Do not add more workflows until the existing catalog is contract-clean.
- Do not expand the service list without a documented API, health check, and ownership of the runtime path.

## Suggested Order

1. Finish contract alignment and regression tests.
2. Canonicalize the daemon and dashboard path.
3. Harden the top workflows.
4. Clean up install and platform boundaries.
