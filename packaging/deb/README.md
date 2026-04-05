# Debian Packaging

This directory contains the first real Linux desktop package path for the
canonical ClawOS Command Center experience.

## Build

```bash
bash packaging/deb/build_deb.sh
```

To reuse an already-built frontend bundle:

```bash
bash packaging/deb/build_deb.sh --skip-frontend-build
```

## Output

The build writes:

- `dist/clawos-command-center_<version>_amd64.deb`
- `dist/clawos-command-center_<version>_amd64.deb.sha256`

## What Gets Installed

- `/opt/clawos` with the application source and built frontend
- `/usr/bin/clawos-command-center`
- `/usr/bin/clawos-setup`
- `/usr/bin/clawos`
- `/usr/bin/clawctl`
- `/usr/bin/nexus`
- `/usr/share/applications/clawos-command-center.desktop`
- `/etc/xdg/autostart/clawos-setup.desktop`
