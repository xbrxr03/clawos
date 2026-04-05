# ClawOS Desktop Shell

This directory hosts the Tauri shell for ClawOS Command Center and ClawOS Setup.

The frontend source of truth remains `dashboard/frontend`.

## Intended Use

- Linux desktop shell for Ubuntu/Debian installs
- macOS desktop shell for Apple Silicon installs
- native helpers for logs, support bundles, and service control

## Build Contract

- dev frontend: `http://localhost:5173`
- production frontend: `services/dashd/static`

## Commands

```bash
cd desktop/command-center
npm install
npm run dev
```

For a packaged desktop shell build:

```bash
cd desktop/command-center
npm install
npm run build
```
