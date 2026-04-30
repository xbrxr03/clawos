#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Build ClawOS bootable ISO
# Requires: ubuntu-desktop-amd64.iso as base, sudo access

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../" && pwd)"
BUILD_DIR="${BUILD_DIR:-/tmp/clawos-iso-build}"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/dist}"

# Colors
G="\033[38;5;84m"; R="\033[38;5;203m"; B="\033[38;5;75m"
Y="\033[38;5;220m"; RESET="\033[0m"; BOLD="\033[1m"

log() { echo -e "${B}$1${RESET} $2"; }
ok() { echo -e "  ${G}✓${RESET} $1"; }
fail() { echo -e "  ${R}✗${RESET} $1"; exit 1; }
info() { echo -e "  ${D}..${RESET} $1"; }

log "🔨" "ClawOS ISO Builder"
echo "======================"
echo ""

# Check prerequisites
if ! command -v xorriso &>/dev/null; then
    log "📦" "Installing build dependencies..."
    sudo apt-get update
    sudo apt-get install -y xorriso squashfs-tools genisoimage
fi

# Find base ISO
BASE_ISO="${BASE_ISO:-}"
if [[ -z "$BASE_ISO" ]]; then
    # Try common locations
    for path in "$HOME/Downloads/ubuntu-24.04-desktop-amd64.iso" \
                "$HOME/Downloads/ubuntu-22.04-desktop-amd64.iso" \
                "/tmp/ubuntu-24.04-desktop-amd64.iso"; do
        if [[ -f "$path" ]]; then
            BASE_ISO="$path"
            break
        fi
    done
fi

if [[ -z "$BASE_ISO" ]] || [[ ! -f "$BASE_ISO" ]]; then
    fail "Base Ubuntu ISO not found. Set BASE_ISO=/path/to/ubuntu.iso"
fi

ok "Base ISO: $BASE_ISO"

# Setup build directory
log "📁" "Setting up build directory: $BUILD_DIR"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"/{iso,new,overlay}

# Mount and extract ISO
log "📀" "Extracting base ISO..."
MOUNT_POINT="$BUILD_DIR/mnt"
mkdir -p "$MOUNT_POINT"

if mountpoint -q "$MOUNT_POINT"; then
    sudo umount "$MOUNT_POINT" || true
fi

sudo mount -o loop,ro "$BASE_ISO" "$MOUNT_POINT" || fail "Failed to mount ISO"
rsync -a "$MOUNT_POINT/" "$BUILD_DIR/iso/" || fail "Failed to copy ISO contents"
sudo umount "$MOUNT_POINT" || true

ok "ISO extracted"

# Prepare ClawOS overlay
log "🔧" "Preparing ClawOS overlay..."

# Create squashfs overlay with ClawOS files
OVERLAY_DIR="$BUILD_DIR/overlay/clawos"
mkdir -p "$OVERLAY_DIR"/{opt/clawos,etc/systemd/system,etc/clawos}

# Copy ClawOS runtime
cp -r "$REPO_ROOT"/* "$OVERLAY_DIR/opt/clawos/" 2>/dev/null || true

# Create systemd service for auto-start
cat > "$OVERLAY_DIR/etc/systemd/system/clawos.service" << 'EOF'
[Unit]
Description=ClawOS Agent System
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/clawos/scripts/dev_boot.sh --systemd
RemainAfterExit=yes
User=clawos
Group=clawos

[Install]
WantedBy=multi-user.target
EOF

# Create first-boot script
cat > "$OVERLAY_DIR/opt/clawos/scripts/first-boot.sh" << 'EOF'
#!/bin/bash
# First boot configuration
set -e

# Create clawos user if doesn't exist
if ! id -u clawos &>/dev/null; then
    useradd -m -s /bin/bash -G sudo clawos
    echo "clawos:clawos" | chpasswd
fi

# Run installer as clawos user
su - clawos -c "cd /opt/clawos && bash install.sh --skip-model"

# Enable systemd service
systemctl enable clawos.service

# Mark first boot complete
touch /var/lib/clawos/.first-boot-complete
EOF

chmod +x "$OVERLAY_DIR/opt/clawos/scripts/first-boot.sh"

# Create preseed for auto-install (optional)
cat > "$OVERLAY_DIR/etc/clawos/preseed.cfg" << 'EOF'
# ClawOS preseed configuration
d-i debian-installer/locale string en_US
d-i keyboard-configuration/xkb-keymap select us
d-i netcfg/choose_interface select auto
d-i netcfg/get_hostname string clawos
d-i netcfg/get_domain string local
d-i mirror/country string manual
d-i mirror/http/hostname string archive.ubuntu.com
d-i mirror/http/directory string /ubuntu
d-i mirror/http/proxy string
d-i passwd/user-fullname string ClawOS User
d-i passwd/username string clawos
d-i passwd/user-password password clawos
d-i passwd/user-password-again password clawos
d-i user-setup/allow-password-weak boolean true
d-i clock-setup/utc boolean true
d-i time/zone string UTC
d-i clock-setup/ntp boolean true
d-i partman-auto/method string regular
d-i partman-lvm/device_remove_lvm boolean true
d-i partman-md/device_remove_md boolean true
d-i partman-auto/choose_recipe select atomic
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true
d-i pkgsel/include string curl git python3 python3-pip nodejs npm sqlite3
EOF

# Build squashfs
cd "$BUILD_DIR/overlay"
mksquashfs clawos "$BUILD_DIR/iso/casper/clawos.squashfs" -comp xz -e .git

ok "Overlay created"

# Modify GRUB config for ClawOS branding
log "🎨" "Applying ClawOS branding..."

# Update grub.cfg
if [[ -f "$BUILD_DIR/iso/boot/grub/grub.cfg" ]]; then
    sed -i 's/Ubuntu/ClawOS/g' "$BUILD_DIR/iso/boot/grub/grub.cfg"
    sed -i 's/Try Ubuntu without installing/Try ClawOS without installing/g' "$BUILD_DIR/iso/boot/grub/grub.cfg"
    sed -i 's/Install Ubuntu/Install ClawOS/g' "$BUILD_DIR/iso/boot/grub/grub.cfg"
fi

# Update isolinux
if [[ -f "$BUILD_DIR/iso/isolinux/txt.cfg" ]]; then
    sed -i 's/Ubuntu/ClawOS/g' "$BUILD_DIR/iso/isolinux/txt.cfg"
fi

ok "Branding applied"

# Repack ISO
log "📦" "Building final ISO..."
mkdir -p "$OUTPUT_DIR"

OUTPUT_ISO="$OUTPUT_DIR/clawos-0.1.0-amd64.iso"

# Create ISO with xorriso
xorriso -as mkisofs \
    -r -V "ClawOS 0.1.0" \
    -J -J -joliet-long \
    -cache-inodes \
    -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    -eltorito-alt-boot \
    -e boot/grub/efi.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -isohybrid-apm-hfsplus \
    -o "$OUTPUT_ISO" \
    "$BUILD_DIR/iso" 2>&1 | grep -v "^xorriso " || true

if [[ -f "$OUTPUT_ISO" ]]; then
    ok "ISO created: $OUTPUT_ISO"
    ls -lh "$OUTPUT_ISO"
    
    # Calculate checksums
    cd "$OUTPUT_DIR"
    sha256sum "$(basename "$OUTPUT_ISO")" > "$(basename "$OUTPUT_ISO").sha256"
    ok "Checksums created"
else
    fail "ISO build failed"
fi

# Cleanup
log "🧹" "Cleaning up..."
rm -rf "$BUILD_DIR"
ok "Build directory cleaned"

echo ""
echo "======================"
log "🎉" "Build complete!"
echo ""
echo "Output: $OUTPUT_ISO"
echo ""
echo "To test:"
echo "  qemu-system-x86_64 -cdrom $OUTPUT_ISO -m 4096"
echo ""
echo "To flash to USB:"
echo "  sudo dd if=$OUTPUT_ISO of=/dev/sdX bs=4M status=progress"
