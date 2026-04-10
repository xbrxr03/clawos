#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS ISO hook 04 — Install desktop environment (Desktop edition only)
# Server edition skips this hook.
set -uo pipefail

EDITION="${CLAWOS_EDITION:-desktop}"

if [ "$EDITION" != "desktop" ]; then
    echo "[ClawOS hook 04] Server edition — skipping desktop install"
    exit 0
fi

echo "[ClawOS hook 04] Installing XFCE desktop environment..."

export DEBIAN_FRONTEND=noninteractive

apt-get install -y -qq \
    xfce4 xfce4-goodies \
    lightdm lightdm-gtk-greeter \
    xorg \
    chromium-browser \
    fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
    2>&1 | tail -5

# Configure LightDM for auto-login on first boot
# (first-run wizard disables auto-login after setup completes)
cat > /etc/lightdm/lightdm.conf.d/clawos.conf <<'EOF'
[SeatDefaults]
autologin-user=clawos
autologin-user-timeout=0
user-session=xfce
greeter-session=lightdm-gtk-greeter
EOF

# Set ClawOS wallpaper as XFCE background
if [ -f /opt/clawos/assets/wallpaper.png ]; then
    mkdir -p /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/
    cat > /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="backdrop" type="empty">
    <property name="screen0" type="empty">
      <property name="monitorVirtual1" type="empty">
        <property name="workspace0" type="empty">
          <property name="last-image" type="string" value="/opt/clawos/assets/wallpaper.png"/>
          <property name="image-style" type="int" value="5"/>
        </property>
      </property>
    </property>
  </property>
</channel>
EOF
fi

# Enable LightDM
systemctl enable lightdm 2>/dev/null || true

echo "[hook 04] Desktop environment installed."
