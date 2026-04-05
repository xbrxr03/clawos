# ClawOS Figma System

The Figma file is the visual source of truth for ClawOS. The repository is the shipping source of truth.

## File Name

`ClawOS Command Center`

## Figma Pages

1. `01 Foundations`
2. `02 Components`
3. `03 Setup`
4. `04 Command Center`
5. `05 Motion + Specs`
6. `06 Handoff + Code Connect`

## Required Foundations

- dark and light token definitions
- typography scale
- spacing scale
- radius, elevation, blur, and border rules
- semantic status colors
- window chrome and panel chrome rules

## Required Code Sync

- Figma component names must match React component names.
- Figma variants must map to code props/states.
- Tokens must exist in both Figma and `dashboard/frontend/src/design`.
- Code Connect mappings are added after core components stabilize.

## Product Rules

- Monterey-inspired interaction grammar
- Finder/Xcode-style shell hierarchy
- Apple-like device onboarding for setup
- no copied Apple branding or proprietary assets
