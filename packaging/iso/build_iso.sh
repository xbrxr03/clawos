#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS ISO Builder — builds bootable ISO from Ubuntu 24.04 minimal
# Usage: sudo bash packaging/iso/build_iso.sh [--skip-download]
set -euo pipefail

VERSION="${CLAWOS_VERSION:-0.1.0}"
UBUNTU_BASE="ubuntu-24.04.4-live-server-amd64.iso"
UBUNTU_URL="https://releases.ubuntu.com/24.04/${UBUNTU_BASE}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="/tmp/clawos-build-${VERSION}"
DIST_DIR="${PROJECT_DIR}/dist"
OUTPUT_ISO="${DIST_DIR}/clawos-${VERSION}-amd64.iso"
CHROOT="${BUILD_DIR}/edit"
SKIP_DOWNLOAD=false
for arg in "$@"; do [[ "$arg" == "--skip-download" ]] && SKIP_DOWNLOAD=true; done

G="\033[0;32m" N="\033[0m" R="\033[0;31m"
step() { echo -e "\n  \033[0;34m──\033[0m $1"; }
ok()   { echo -e "  ${G}✓${N}  $1"; }
die()  { echo -e "  ${R}✗${N}  $1"; exit 1; }

cat << 'BANNER'

  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝
  ClawOS ISO Builder
BANNER

[[ "$EUID" -ne 0 ]] && die "Must run as root: sudo bash packaging/iso/build_iso.sh"

step "Build deps"
apt-get install -y -qq xorriso squashfs-tools grub-pc-bin grub-efi-amd64-bin wget curl
ok "Build deps ready"

step "Ubuntu 24.04 base"
if [[ "$SKIP_DOWNLOAD" == "true" ]] && [[ -f "$UBUNTU_BASE" ]]; then
  ok "Reusing ${UBUNTU_BASE}"
elif [[ ! -f "$UBUNTU_BASE" ]]; then
  echo "  Downloading (~1.5GB) ..."
  wget -q --show-progress "$UBUNTU_URL" -O "$UBUNTU_BASE" || die "Download failed"
  ok "Downloaded"
else
  ok "${UBUNTU_BASE} present"
fi

step "Extracting ISO"
rm -rf "$BUILD_DIR"; mkdir -p "$BUILD_DIR/iso" "$CHROOT" "$DIST_DIR"
MP="/mnt/clawos-ubuntu-$$"; mkdir -p "$MP"
mount -o loop,ro "$UBUNTU_BASE" "$MP"
cp -a "${MP}/." "${BUILD_DIR}/iso/"; umount "$MP"; rmdir "$MP"
chmod -R u+w "${BUILD_DIR}/iso"
SQUASHFS="${BUILD_DIR}/iso/casper/filesystem.squashfs"
[[ -f "$SQUASHFS" ]] || die "filesystem.squashfs not found"
echo "  Extracting filesystem (~5 min) ..."
unsquashfs -q -d "$CHROOT" "$SQUASHFS"
ok "Extracted"

step "Chroot setup"
for m in dev dev/pts proc sys run; do mount --bind "/${m}" "${CHROOT}/${m}"; done
cp --remove-destination /etc/resolv.conf "${CHROOT}/etc/resolv.conf"
cp -r "$PROJECT_DIR" "${CHROOT}/opt/clawos"
cp "${SCRIPT_DIR}/chroot_install.sh" "${CHROOT}/tmp/chroot_install.sh"
chmod +x "${CHROOT}/tmp/chroot_install.sh"
ok "Chroot ready"

step "Installing ClawOS (~15 min)"
chroot "$CHROOT" /tmp/chroot_install.sh || die "chroot_install.sh failed"
ok "ClawOS installed"

step "Cleanup"
chroot "$CHROOT" apt-get clean -qq
for m in run sys proc dev/pts dev; do umount "${CHROOT}/${m}" 2>/dev/null || true; done
rm -f "${CHROOT}/tmp/chroot_install.sh" "${CHROOT}/etc/resolv.conf"
ok "Cleaned"

step "Repack squashfs (~10 min)"
rm -f "$SQUASHFS"
mksquashfs "$CHROOT" "$SQUASHFS" -comp xz -Xbcj x86 -b 1M -noappend -quiet 2>/dev/null
printf "%s" "$(du -sx --block-size=1 "$CHROOT" | cut -f1)" > "${BUILD_DIR}/iso/casper/filesystem.size"
echo "ClawOS ${VERSION}" > "${BUILD_DIR}/iso/.disk/info"
cd "${BUILD_DIR}/iso"
find . -type f -not -name 'md5sum.txt' -exec md5sum {} \; > md5sum.txt
cd "$PROJECT_DIR"
ok "Squashfs repacked"

step "Building bootable ISO"
xorriso -as mkisofs \
  -r -V "ClawOS ${VERSION}" \
  --grub2-mbr "${BUILD_DIR}/iso/boot/grub/i386-pc/boot_hybrid.img" \
  -partition_offset 16 --mbr-force-bootable \
  -append_partition 2 28732ac11ff8d211ba4b00a0c93ec93b \
    "${BUILD_DIR}/iso/boot/grub/efi.img" \
  -appended_part_as_gpt \
  -iso_mbr_part_type a2a0d0ebe5b9334487c068b6b72699c7 \
  -c '/boot.catalog' \
  -b '/boot/grub/i386-pc/eltorito.img' \
  -no-emul-boot -boot-load-size 4 -boot-info-table --grub2-boot-info \
  -eltorito-alt-boot \
  -e '--interval:appended_partition_2:::' \
  -no-emul-boot \
  -o "$OUTPUT_ISO" "${BUILD_DIR}/iso" 2>&1 | tail -3

SHA=$(sha256sum "$OUTPUT_ISO" | cut -d' ' -f1)
echo "$SHA  clawos-${VERSION}-amd64.iso" > "${OUTPUT_ISO}.sha256"
SIZE=$(du -sh "$OUTPUT_ISO" | cut -f1)

echo ""
echo -e "  ${G}✓  clawos-${VERSION}-amd64.iso${N}  (${SIZE})"
echo "  SHA256: ${SHA:0:24}..."
echo ""
echo "  Flash:  sudo dd if=${OUTPUT_ISO} of=/dev/sdX bs=4M status=progress oflag=sync"
echo ""
