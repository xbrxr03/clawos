#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate comparison PNG using Pillow."""
from PIL import Image, ImageDraw, ImageFont

img = Image.new('RGB', (1200, 800), (10, 0, 0))
draw = ImageDraw.Draw(img)

# Simple gradient
for y in range(800):
    r = int(26 * (y / 800))
    draw.line([(0, y), (1200, y)], fill=(r, 8, 8))

try:
    font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    font_header = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    font_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 15)
    font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    font_mono = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 13)
except Exception:
    font_title = font_header = font_body = font_small = font_mono = ImageFont.load_default()

# Title
draw.text((600, 50), "🦀 ClawOS vs the field", fill=(245, 240, 240), font=font_title, anchor="mm")
draw.rectangle([500, 68, 700, 70], fill=(229, 57, 53))

# Table header
draw.rounded_rectangle([50, 100, 1150, 144], radius=8, fill=(229, 57, 53, 20))
draw.text((250, 122), "FEATURE", fill=(229, 57, 53), font=font_header, anchor="mm")
draw.text((500, 122), "🦀 CLAWOS", fill=(229, 57, 53), font=font_header, anchor="mm")
draw.text((700, 122), "ODYSSEUS", fill=(154, 136, 136), font=font_header, anchor="mm")
draw.text((880, 122), "OPEN WEBUI", fill=(154, 136, 136), font=font_header, anchor="mm")
draw.text((1060, 122), "JAN", fill=(154, 136, 136), font=font_header, anchor="mm")

# Table data
rows = [
    ("Voice Activation", "✅ Hey Claw", "❌", "❌", "❌"),
    ("Approval Gates", "✅ Native popup", "❌ Shell access", "❌", "❌"),
    ("Agent Workflows", "✅ 29 built-in", "✅ Skills", "❌", "❌"),
    ("Multi-Agent (A2A)", "✅ Agent mesh", "❌ Single agent", "❌", "❌"),
    ("Structured Memory", "✅ 7 layers", "⚠️ Flat vectors", "⚠️ Flat", "⚠️ Flat"),
    ("Bootable ISO", "✅ Flash & go", "❌", "❌", "❌"),
    ("Zero Telemetry", "✅ Verify it", "✅", "✅", "✅"),
]

GREEN = (34, 197, 94)
RED = (74, 58, 58)
GRAY = (154, 136, 136)
WHITE = (245, 240, 240)

y = 160
for i, (feat, claw, ody, owui, jan) in enumerate(rows):
    bg = (229, 57, 53, 8) if i % 2 == 0 else None
    if bg:
        draw.rectangle([50, y-10, 1150, y+30], fill=(18, 8, 8))

    draw.text((250, y+10), feat, fill=GRAY, font=font_body, anchor="mm")
    draw.text((500, y+10), claw, fill=GREEN, font=font_body, anchor="mm")
    col3 = GREEN if "✅" in ody else RED
    draw.text((700, y+10), ody, fill=col3, font=font_body, anchor="mm")
    col4 = GREEN if "✅" in owui else RED
    draw.text((880, y+10), owui, fill=col4, font=font_body, anchor="mm")
    col5 = GREEN if "✅" in jan else RED
    draw.text((1060, y+10), jan, fill=col5, font=font_body, anchor="mm")
    y += 44

# Divider
draw.rectangle([50, y+10, 1150, y+11], fill=(229, 57, 53, 40))

# CTA
draw.text((600, y+50), "Ollama gave you a local model.", fill=WHITE, font=font_title, anchor="mm")
draw.text((600, y+90), "ClawOS gives you a local agent.", fill=(229, 57, 53), font=font_title, anchor="mm")

# Install command
draw.rounded_rectangle([350, y+120, 850, y+164], radius=10, fill=(229, 57, 53, 20), outline=(229, 57, 53, 50))
draw.text((600, y+142), "curl -fsSL https://clawos.ai/install.sh | bash", fill=(255, 107, 107), font=font_mono, anchor="mm")

# Bottom
draw.text((600, 700), "github.com/xbrxr03/clawos · Open Source · AGPL-3.0", fill=(74, 58, 58), font=font_small, anchor="mm")

# Corner brackets
for (x1, y1, x2, y2) in [(30,30,50,10), (1170,30,1150,10), (30,770,50,790), (1170,770,1150,790)]:
    draw.line([(x1, y1), (x2 if x1==30 else x1, y1)], fill=(229, 57, 53, 80), width=1)
    draw.line([(x1, y1), (x1, y2 if y1==30 else y1)], fill=(229, 57, 53, 80), width=1)

img.save("/Users/abrarhabib/Projects/clawos/landing/comparison.png", "PNG")
print("comparison.png saved (1200x800)")