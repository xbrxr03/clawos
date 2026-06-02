#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate social media assets for ClawOS."""
import os
from pathlib import Path

# Generate SVG social card (1200x630 for GitHub/Twitter)
SOCIAL_CARD = '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0a0000"/>
      <stop offset="50%" style="stop-color:#1a0808"/>
      <stop offset="100%" style="stop-color:#0a0000"/>
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#e53935"/>
      <stop offset="100%" style="stop-color:#ff6b6b"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="40%" r="50%">
      <stop offset="0%" style="stop-color:#e53935;stop-opacity:0.15"/>
      <stop offset="100%" style="stop-color:#0a0000;stop-opacity:0"/>
    </radialGradient>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect width="1200" height="630" fill="url(#glow)"/>

  <!-- Scan line -->
  <line x1="0" y1="315" x2="1200" y2="315" stroke="#e53935" stroke-opacity="0.06" stroke-width="1"/>

  <!-- Corner brackets -->
  <path d="M40 40 L40 20 L60 20" stroke="#e53935" stroke-width="1.5" fill="none" opacity="0.4"/>
  <path d="M1160 40 L1160 20 L1140 20" stroke="#e53935" stroke-width="1.5" fill="none" opacity="0.4"/>
  <path d="M40 590 L40 610 L60 610" stroke="#e53935" stroke-width="1.5" fill="none" opacity="0.4"/>
  <path d="M1160 590 L1160 610 L1140 610" stroke="#e53935" stroke-width="1.5" fill="none" opacity="0.4"/>

  <!-- Crab emoji -->
  <text x="600" y="200" text-anchor="middle" font-size="80">🦀</text>

  <!-- Title -->
  <text x="600" y="290" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-weight="800" font-size="56" fill="#f5f0f0" letter-spacing="-2">
    ClawOS
  </text>

  <!-- Tagline -->
  <text x="600" y="340" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-weight="400" font-size="24" fill="#9a8888">
    Your laptop. Your AI. Your rules.
  </text>

  <!-- Accent line -->
  <rect x="520" y="365" width="160" height="3" rx="1.5" fill="url(#accent)"/>

  <!-- Feature badges -->
  <g transform="translate(600, 420)" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif">
    <!-- Row 1 -->
    <rect x="-400" y="-14" width="160" height="28" rx="14" fill="rgba(229,57,53,0.12)" stroke="rgba(229,57,53,0.25)" stroke-width="1"/>
    <text x="-320" y="5" font-size="12" font-weight="600" fill="#ff6b6b">🗣️ Voice Activation</text>

    <rect x="-220" y="-14" width="160" height="28" rx="14" fill="rgba(229,57,53,0.12)" stroke="rgba(229,57,53,0.25)" stroke-width="1"/>
    <text x="-140" y="5" font-size="12" font-weight="600" fill="#ff6b6b">🛡️ Approval Gates</text>

    <rect x="-40" y="-14" width="160" height="28" rx="14" fill="rgba(229,57,53,0.12)" stroke="rgba(229,57,53,0.25)" stroke-width="1"/>
    <text x="40" y="5" font-size="12" font-weight="600" fill="#ff6b6b">🧠 7-Layer Memory</text>

    <rect x="140" y="-14" width="160" height="28" rx="14" fill="rgba(229,57,53,0.12)" stroke="rgba(229,57,53,0.25)" stroke-width="1"/>
    <text x="220" y="5" font-size="12" font-weight="600" fill="#ff6b6b">🤖 Agent Mesh</text>

    <!-- Row 2 -->
    <rect x="-310" y="26" width="160" height="28" rx="14" fill="rgba(34,197,94,0.10)" stroke="rgba(34,197,94,0.20)" stroke-width="1"/>
    <text x="-230" y="45" font-size="12" font-weight="600" fill="#22c55e">⚡ 29 Workflows</text>

    <rect x="-130" y="26" width="160" height="28" rx="14" fill="rgba(34,197,94,0.10)" stroke="rgba(34,197,94,0.20)" stroke-width="1"/>
    <text x="-50" y="45" font-size="12" font-weight="600" fill="#22c55e">🔒 Zero Telemetry</text>

    <rect x="50" y="26" width="160" height="28" rx="14" fill="rgba(34,197,94,0.10)" stroke="rgba(34,197,94,0.20)" stroke-width="1"/>
    <text x="130" y="45" font-size="12" font-weight="600" fill="#22c55e">💿 Bootable ISO</text>
  </g>

  <!-- Bottom text -->
  <text x="600" y="540" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-size="14" fill="#4a3a3a">
    Open Source · AGPL-3.0 · Self-hosted · Zero cloud
  </text>

  <!-- URL -->
  <text x="600" y="575" text-anchor="middle" font-family="'SF Mono','Fira Code',monospace" font-size="13" fill="#9a8888">
    github.com/xbrxr03/clawos
  </text>
</svg>'''

# Generate comparison graphic (wider format for Reddit/HN)
COMPARISON_CARD = '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <defs>
    <linearGradient id="bg2" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0a0000"/>
      <stop offset="100%" style="stop-color:#1a0808"/>
    </linearGradient>
  </defs>

  <rect width="1200" height="800" fill="url(#bg2)"/>

  <!-- Title -->
  <text x="600" y="60" text-anchor="middle" font-family="system-ui,sans-serif" font-weight="800" font-size="36" fill="#f5f0f0">
    🦀 ClawOS vs the field
  </text>
  <rect x="500" y="72" width="200" height="2" rx="1" fill="#e53935" opacity="0.5"/>

  <!-- Table header -->
  <rect x="50" y="100" width="1100" height="44" rx="8" fill="rgba(229,57,53,0.08)"/>
  <text x="250" y="128" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="700" fill="#e53935">FEATURE</text>
  <text x="500" y="128" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="700" fill="#e53935">🦀 CLAWOS</text>
  <text x="700" y="128" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="700" fill="#9a8888">ODYSSEUS</text>
  <text x="880" y="128" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="700" fill="#9a8888">OPEN WEBUI</text>
  <text x="1060" y="128" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="700" fill="#9a8888">JAN</text>

  <!-- Table rows -->
  <g font-family="system-ui,sans-serif" font-size="15">
    <!-- Voice -->
    <rect x="50" y="152" width="1100" height="40" rx="0" fill="rgba(229,57,53,0.03)"/>
    <text x="250" y="178" text-anchor="middle" fill="#9a8888">Voice Activation</text>
    <text x="500" y="178" text-anchor="middle" fill="#22c55e" font-weight="600">✅ "Hey Claw"</text>
    <text x="700" y="178" text-anchor="middle" fill="#4a3a3a">❌</text>
    <text x="880" y="178" text-anchor="middle" fill="#4a3a3a">❌</text>
    <text x="1060" y="178" text-anchor="middle" fill="#4a3a3a">❌</text>

    <!-- Approval -->
    <rect x="50" y="196" width="1100" height="40" rx="0" fill="none"/>
    <text x="250" y="222" text-anchor="middle" fill="#9a8888">Approval Gates</text>
    <text x="500" y="222" text-anchor="middle" fill="#22c55e" font-weight="600">✅ Native popup</text>
    <text x="700" y="222" text-anchor="middle" fill="#4a3a3a">❌ Shell access</text>
    <text x="880" y="222" text-anchor="middle" fill="#4a3a3a">❌</text>
    <text x="1060" y="222" text-anchor="middle" fill="#4a3a3a">❌</text>

    <!-- Workflows -->
    <rect x="50" y="240" width="1100" height="40" rx="0" fill="rgba(229,57,53,0.03)"/>
    <text x="250" y="266" text-anchor="middle" fill="#9a8888">Agent Workflows</text>
    <text x="500" y="266" text-anchor="middle" fill="#22c55e" font-weight="600">✅ 29 built-in</text>
    <text x="700" y="266" text-anchor="middle" fill="#22c55e">✅ Skills</text>
    <text x="880" y="266" text-anchor="middle" fill="#4a3a3a">❌</text>
    <text x="1060" y="266" text-anchor="middle" fill="#4a3a3a">❌</text>

    <!-- A2A -->
    <rect x="50" y="284" width="1100" height="40" rx="0" fill="none"/>
    <text x="250" y="310" text-anchor="middle" fill="#9a8888">Multi-Agent (A2A)</text>
    <text x="500" y="310" text-anchor="middle" fill="#22c55e" font-weight="600">✅ Agent mesh</text>
    <text x="700" y="310" text-anchor="middle" fill="#4a3a3a">❌ Single agent</text>
    <text x="880" y="310" text-anchor="middle" fill="#4a3a3a">❌</text>
    <text x="1060" y="310" text-anchor="middle" fill="#4a3a3a">❌</text>

    <!-- Memory -->
    <rect x="50" y="328" width="1100" height="40" rx="0" fill="rgba(229,57,53,0.03)"/>
    <text x="250" y="354" text-anchor="middle" fill="#9a8888">Structured Memory</text>
    <text x="500" y="354" text-anchor="middle" fill="#22c55e" font-weight="600">✅ 7 layers</text>
    <text x="700" y="354" text-anchor="middle" fill="#9a8888">⚠️ Flat vectors</text>
    <text x="880" y="354" text-anchor="middle" fill="#9a8888">⚠️ Flat</text>
    <text x="1060" y="354" text-anchor="middle" fill="#9a8888">⚠️ Flat</text>

    <!-- Bootable ISO -->
    <rect x="50" y="372" width="1100" height="40" rx="0" fill="none"/>
    <text x="250" y="398" text-anchor="middle" fill="#9a8888">Bootable ISO</text>
    <text x="500" y="398" text-anchor="middle" fill="#22c55e" font-weight="600">✅ Flash &amp; go</text>
    <text x="700" y="398" text-anchor="middle" fill="#4a3a3a">❌</text>
    <text x="880" y="398" text-anchor="middle" fill="#4a3a3a">❌</text>
    <text x="1060" y="398" text-anchor="middle" fill="#4a3a3a">❌</text>

    <!-- Zero telemetry -->
    <rect x="50" y="416" width="1100" height="40" rx="0" fill="rgba(229,57,53,0.03)"/>
    <text x="250" y="442" text-anchor="middle" fill="#9a8888">Zero Telemetry</text>
    <text x="500" y="442" text-anchor="middle" fill="#22c55e" font-weight="600">✅ Verify it</text>
    <text x="700" y="442" text-anchor="middle" fill="#22c55e">✅</text>
    <text x="880" y="442" text-anchor="middle" fill="#22c55e">✅</text>
    <text x="1060" y="442" text-anchor="middle" fill="#22c55e">✅</text>
  </g>

  <!-- Bottom line -->
  <rect x="50" y="470" width="1100" height="1" fill="rgba(229,57,53,0.15)"/>

  <!-- CTA -->
  <text x="600" y="520" text-anchor="middle" font-family="system-ui,sans-serif" font-size="22" font-weight="700" fill="#f5f0f0">
    Ollama gave you a local model.
  </text>
  <text x="600" y="555" text-anchor="middle" font-family="system-ui,sans-serif" font-size="22" font-weight="700" fill="#e53935">
    ClawOS gives you a local agent.
  </text>

  <!-- Install command -->
  <rect x="350" y="590" width="500" height="44" rx="10" fill="rgba(229,57,53,0.08)" stroke="rgba(229,57,53,0.20)" stroke-width="1"/>
  <text x="600" y="618" text-anchor="middle" font-family="'SF Mono','Fira Code',monospace" font-size="14" fill="#ff6b6b">
    curl -fsSL https://clawos.ai/install.sh | bash
  </text>

  <!-- URL -->
  <text x="600" y="700" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" fill="#4a3a3a">
    github.com/xbrxr03/clawos · Open Source · AGPL-3.0
  </text>

  <!-- Corner brackets -->
  <path d="M30 30 L30 10 L50 10" stroke="#e53935" stroke-width="1" fill="none" opacity="0.3"/>
  <path d="M1170 30 L1170 10 L1150 10" stroke="#e53935" stroke-width="1" fill="none" opacity="0.3"/>
  <path d="M30 770 L30 790 L50 790" stroke="#e53935" stroke-width="1" fill="none" opacity="0.3"/>
  <path d="M1170 770 L1170 790 L1150 790" stroke="#e53935" stroke-width="1" fill="none" opacity="0.3"/>
</svg>'''

output_dir = Path("~/Projects/clawos/landing").expanduser()
(output_dir / "og.svg").write_text(SOCIAL_CARD)
(output_dir / "comparison.svg").write_text(COMPARISON_CARD)

# Convert SVGs to PNG using Pillow (render as raster fallback)
try:
    from PIL import Image, ImageDraw, ImageFont
    # Generate a simple PNG social card as fallback
    img = Image.new('RGB', (1200, 630), (10, 0, 0))
    draw = ImageDraw.Draw(img)

    # Simple gradient overlay
    for y in range(630):
        r = int(26 * (y / 630))
        draw.line([(0, y), (1200, y)], fill=(r, 8, 8))

    # Add text
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 56)
        font_med = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        font_mono = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 13)
    except:
        font_large = ImageFont.load_default()
        font_med = font_small = font_mono = font_large

    draw.text((600, 120), "🦀", fill=(255, 255, 255), font=font_large, anchor="mm")
    draw.text((600, 220), "ClawOS", fill=(245, 240, 240), font=font_large, anchor="mm")
    draw.text((600, 290), "Your laptop. Your AI. Your rules.", fill=(154, 136, 136), font=font_med, anchor="mm")

    # Accent line
    draw.rectangle([520, 310, 680, 313], fill=(229, 57, 53))

    # Features
    features = [
        "🗣 Voice Activation  ·  🛡 Approval Gates  ·  🧠 7-Layer Memory",
        "🤖 Agent Mesh  ·  ⚡ 29 Workflows  ·  🔒 Zero Telemetry"
    ]
    y = 360
    for line in features:
        draw.text((600, y), line, fill=(255, 140, 140), font=font_med, anchor="mm")
        y += 35

    draw.text((600, 500), "Open Source · AGPL-3.0 · Self-hosted · Zero cloud", fill=(170, 140, 140), font=font_small, anchor="mm")
    draw.text((600, 570), "github.com/xbrxr03/clawos", fill=(200, 170, 170), font=font_mono, anchor="mm")

    img.save(output_dir / "og.png", "PNG")
    print("Generated og.png (1200x630)")
except Exception as e:
    print(f"PNG generation skipped: {e}")

print("Generated og.svg and comparison.svg")