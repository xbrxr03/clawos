# ClawOS Launch Checklist — Human Tasks Only

> Everything in this list requires you (the human) on a real Linux dev
> box, real accounts, or real-world action. Code-only tasks have already
> been completed. Order matters: 1 → 7 in sequence.

---

## 1. Spin up a clean Ubuntu 24.04 VM (1 hour)

**Why:** the install hasn't been verified end-to-end since v0.0 was a
different shape. This is the single biggest unknown.

```bash
# Fresh Ubuntu 24.04 desktop VM (8GB RAM minimum)
# Then on the VM:
curl -fsSL https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh | bash
```

Watch for:
- Any step that errors or warns
- The 9-step browser wizard reaching "Welcome home" without manual
  intervention
- All daemons running: `systemctl --user list-units 'clawos-*'`
- `clawctl health` showing green for every service
- `clawctl demos morning-briefing` returning a synthesized briefing

If anything fails, capture the error and fix in code before doing
anything else in this checklist. **Do not proceed to step 2 until this
is clean.**

---

## 2. Set up `install.clawos.io` (30 minutes)

**Why:** the README and all launch copy reference this URL. It must
serve `install.sh` from the GitHub raw URL.

Steps documented in `docs/INSTALL_URL_SETUP.md`. Cheapest path:

1. Buy `clawos.io` domain (Cloudflare, Namecheap, etc. — ~$12/yr)
2. Cloudflare Workers free tier (or any redirector) → set `install`
   subdomain to redirect to:
   `https://raw.githubusercontent.com/xbrxr03/clawos/main/install.sh`
3. Test: `curl -fsSL https://install.clawos.io | head -5` should print
   the `#!/usr/bin/env bash` shebang line of `install.sh`

---

## 3. Record the four demo videos (3 hours)

**Why:** `docs/media/demos/` currently has placeholder files removed.
The launch needs real videos. They are the single most-shared artifact.

Follow `docs/DEMOS.md` exactly — phrases, timings, expected output for
each. Do this on the same Ubuntu VM from step 1 to keep everything
consistent.

For each demo:
1. Run on Ubuntu 24.04, dark theme, 1080p screen
2. Disable wifi for demos 1 + 2 to prove offline credibility
3. Speak naturally, don't perform
4. Don't cut latency — the wait IS the demo

Output files:
```
docs/media/demos/demo1_morning_briefing.{mp4,gif}
docs/media/demos/demo2_essay_editor.{mp4,gif}
docs/media/demos/demo3_approval_popup.{mp4,gif}
docs/media/demos/demo4_quirky_combo.{mp4,gif}
```

After recording, **embed the GIFs into the README** in the Demos section
(currently has a "not yet recorded" placeholder).

Tools:
- `peek` (Linux GIF recorder, simple)
- `obs-studio` (full video, audio)
- `ffmpeg` to convert MP4 → GIF for ≤8MB optimization

---

## 4. Build and upload distribution artifacts (1 hour)

**Why:** users on Ubuntu / Arch / generic Linux need a download path.

```bash
# AppImage (universal Linux)
bash packaging/appimage/build_appimage.sh
# → produces ClawOS-x86_64.AppImage

# Debian/Ubuntu .deb
bash packaging/deb/build_deb.sh
# → produces clawos-command-center_0.1.1_amd64.deb

# Test each on the Ubuntu VM
sudo dpkg -i clawos-command-center_0.1.1_amd64.deb
chmod +x ClawOS-x86_64.AppImage && ./ClawOS-x86_64.AppImage
```

Then on GitHub:
1. Go to https://github.com/xbrxr03/clawos/releases
2. Find the `v0.1.1` tag (already pushed)
3. Click "Edit release"
4. Drag the AppImage and .deb into the release
5. Paste `RELEASE_NOTES_v0.1.1.md` content into the description
6. Publish

For the AUR:
```bash
# Submit packaging/aur/PKGBUILD as clawos-bin to AUR
# Requires AUR account + SSH key
git clone ssh://aur@aur.archlinux.org/clawos-bin.git
cp packaging/aur/PKGBUILD clawos-bin/
cd clawos-bin
makepkg --printsrcinfo > .SRCINFO
git add PKGBUILD .SRCINFO
git commit -m "Initial release v0.1.1"
git push
```

---

## 5. Polish landing page (2 hours)

**Why:** every launch link points at the landing page or the README.

`landing/` directory already has a base. Tasks:
1. Replace placeholder demo videos with the four MP4s from step 3
2. Make the install command big and copy-on-click
3. Add the "zero telemetry" badge prominently
4. Verify links: GitHub repo, releases page, install URL all resolve
5. Deploy to wherever you host it (Vercel, Cloudflare Pages, GitHub Pages)

If `landing/` is incomplete or broken, **don't ship it for v0.1.1** —
just point everything at the GitHub README, which is now polished and
launch-ready. A landing page can be a v0.1.2 follow-up.

---

## 6. Schedule the launch (15 minutes)

**Why:** timing affects 10x reach.

| Channel | Best time | URL |
|---------|-----------|-----|
| **Hacker News** | Tuesday or Wednesday, 8 AM EST | https://news.ycombinator.com/submit |
| **ProductHunt** | Same day as HN, 12:01 AM PT (their day starts) | https://producthunt.com/posts/new |
| **Twitter / X** | Same day, 9 AM EST after HN gets initial traction | manual |

Submission text already drafted:
- HN: `docs/LAUNCH/hn_submission.md`
- PH: `docs/LAUNCH/producthunt.md`
- Twitter: `docs/LAUNCH/twitter_thread.md`

Update each with the real demo GIF URLs after step 3 completes.

---

## 7. Day-of monitoring (2 hours active, half-day passive)

**Why:** HN/PH require quick responses to comments to maintain momentum.

- Monitor HN comments — reply within 15 min for the first 4 hours
- Monitor GitHub issues for installer bugs
- Have the Ubuntu VM warm in case you need to reproduce a user's issue
  on a clean install
- Have `git push` ready for hotfix patches → re-tag `v0.1.1.1` if a
  critical bug surfaces
- Keep Twitter thread thread-jacked with screenshots of HN traction

---

## Optional but high-value (post-launch)

- **Discord server** — referenced in earlier copy but not created. Set
  one up at https://discord.com/developers if traction warrants. Add
  the invite to README only after server has at least one moderator.
- **Telemetry** — opt-in anonymous crash reports help iterate. Skip for
  v0.1.x to maintain "zero telemetry" launch positioning.
- **macOS port** — most code is in place. ~3 days of work for v0.2.
  Apple Developer cert ($99/yr) needed for Gatekeeper.
- **Demo voiceover** — record yourself narrating the demos, publish as
  YouTube video to embed in launch tweet.

---

## Pre-flight before tagging anything new

These are the gates for any future tag (v0.1.2 onwards):

```bash
# Tests green
python -m pytest tests/unit/test_agent_*.py -q     # must be 61+ passing
python -m pytest tests/integration -q              # 7+ passing, skips OK

# Install verified on fresh Ubuntu 24.04
# (manual — see step 1)

# All four demos run end-to-end with real LLM
clawctl demos morning-briefing
clawctl demos essay-editor
clawctl demos approval-test
clawctl demos quirky-combo

# Tauri overlay shows on actual desktop
# (manual visual check)

# README has zero false claims
grep -i "whatsapp\|telegram\|13.700\|13,700\|hey jarvis" README.md
# must return nothing
```

---

## What's already done (don't redo)

✅ README rewritten — zero false claims, accurate architecture, demos
   section with placeholder note
✅ `docs/DEMOS.md` — canonical script per demo
✅ `docs/LAUNCH/{hn,producthunt,twitter}` — drafted, contradictions
   removed
✅ Fake placeholder videos in `docs/media/demos/` removed
✅ `RELEASE_NOTES_v0.1.1.md` written
✅ `v0.1.1` tag exists and pushed
✅ 61 unit tests passing including workspace-escape
✅ systemd units for reminderd + waketrd registered in
   `scripts/setup-systemd.sh`
✅ Shell allowlist hardened (`python3 -c <code>` blocked)
✅ Tauri overlay rebuilt with `show_approval_overlay` command
✅ Structured JSON logging + `clawctl logs`
✅ Distribution scripts (AppImage, .deb, AUR `PKGBUILD`)
✅ ISO builder still working for dedicated-machine path

---

**TL;DR — what's left for you:**

1. Run install on clean Ubuntu, fix anything that breaks (1h)
2. Set up `install.clawos.io` (30m)
3. Record 4 demo videos (3h)
4. Upload AppImage + .deb to GitHub release (1h)
5. Polish landing page or skip for v0.1.2 (2h or 0h)
6. Schedule HN/PH/Twitter (15m)
7. Be online to monitor launch (4h+)

**~7 hours of human work** between you and a real launch.
