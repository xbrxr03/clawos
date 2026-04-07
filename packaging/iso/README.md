# ISO Build Notes

This is the operator runbook for the flagship ClawOS ISO path.

## Current target

- Base image: Ubuntu 24.04 LTS live server (`ubuntu-24.04.4-live-server-amd64.iso`)
- Output artifact: `dist/clawos-<version>-amd64.iso`
- Checksum artifact: `dist/clawos-<version>-amd64.iso.sha256`
- Build host: Linux only

Windows and macOS development checkouts can edit these scripts, but they are not valid ISO build hosts.

## Build prerequisites

- Ubuntu or Debian builder with root access
- `xorriso`
- `squashfs-tools`
- `grub-pc-bin`
- `grub-efi-amd64-bin`
- `wget`
- `curl`

`packaging/iso/build_iso.sh` installs the required packages itself, but the host still needs:

- loop-mount support
- enough free disk for the extracted chroot and rebuilt squashfs
- outbound network access for the Ubuntu base ISO and bootstrap downloads

## Build command

```bash
sudo bash packaging/iso/build_iso.sh
```

To reuse an already-downloaded Ubuntu base image in the repo root:

```bash
sudo bash packaging/iso/build_iso.sh --skip-download
```

## What the script does

1. Downloads or reuses the Ubuntu 24.04 live-server ISO.
2. Mounts and extracts the base ISO.
3. Unsquashes the live filesystem into a writable chroot.
4. Copies the repo into `/opt/clawos` inside the chroot.
5. Runs `packaging/iso/chroot_install.sh` to install ClawOS, build the canonical frontend, and wire first-boot setup surfaces.
6. Rebuilds `filesystem.squashfs`.
7. Re-packs the bootable ISO and writes a SHA256 checksum next to it.

## Validation checklist

The build is not release-ready until all of these are true:

- Boots successfully in a VM before touching hardware.
- Lands in the first-run setup wizard on first boot.
- Calamares assets under `packaging/iso/calamares/` are present and ready for the hardware-validation pass.
- `dashboard/frontend` bundle is present in `services/dashd/static`.
- `clawctl`, `dashd`, `setupd`, and the command-center launcher are available inside the live environment.
- The generated `.sha256` matches the final ISO artifact.

## Still blocked on real validation

The repo now has the build path and packaging assets, but these still require a Linux validation host or real hardware:

- full ISO boot validation on Tier A and Tier B devices
- Calamares install validation end to end
- post-install first boot validation on real hardware
- media flashing validation with the published artifact
