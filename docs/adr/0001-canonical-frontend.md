# ADR 0001: Canonical Frontend

- Status: Accepted
- Date: 2026-04-05

## Decision

`dashboard/frontend` is the single product frontend for ClawOS.

It owns:

- ClawOS Command Center
- ClawOS Setup
- browser fallback/admin access
- shared design tokens and reusable components

## Consequences

- No runtime should serve `clients/dashboard/index.html`.
- No new product UX lands in `archive/legacy/dashboard-backend/`.
- React + TypeScript is the long-term app layer.
- Storybook and Playwright are attached to this frontend only.
