# ADR 0005: Release Artifacts

- Status: Accepted
- Date: 2026-04-05

## Decision

ClawOS ships three primary artifact families:

- `clawos-x.y.z-amd64.iso`
- `clawos-command-center_x.y.z_amd64.deb`
- `ClawOS-Command-Center-x.y.z.dmg`

Secondary artifacts:

- checksums and signatures
- SBOM
- Storybook static build
- support bundle tooling

## Consequences

- ISO remains the flagship appliance experience.
- host installs are first-class entrypoints, not side utilities.
- signing and release automation are required before stable.
