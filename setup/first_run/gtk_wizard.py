#!/usr/bin/env python3
"""
ClawOS GTK4 First-Run Wizard
Runs on first boot from ISO. Replaces terminal wizard for Desktop edition.
Requires: python3-gi, gir1.2-gtk-4.0, gir1.2-adwaita-1
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

WIZARD_DONE_MARKER = Path.home() / ".local" / "share" / "clawos" / "wizard_done"


class ClawOSSetupWindow(Adw.ApplicationWindow):
    SCREENS = [
        "welcome", "hardware", "edition", "model",
        "workspace", "voice", "openclaw", "review", "install", "complete",
    ]

    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("ClawOS Setup")
        self.set_default_size(800, 560)
        self.set_resizable(False)

        self.current = 0
        self.choices = {}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(box)

        self._progress = Gtk.ProgressBar()
        self._progress.set_margin_start(32)
        self._progress.set_margin_end(32)
        self._progress.set_margin_top(16)
        box.append(self._progress)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content.set_vexpand(True)
        box.append(self._content)

        btnbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btnbar.set_margin_start(32)
        btnbar.set_margin_end(32)
        btnbar.set_margin_bottom(24)
        btnbar.set_margin_top(12)
        box.append(btnbar)

        self._back_btn = Gtk.Button(label="Back")
        self._back_btn.connect("clicked", self._on_back)
        btnbar.append(self._back_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        btnbar.append(spacer)

        self._next_btn = Gtk.Button(label="Continue")
        self._next_btn.add_css_class("suggested-action")
        self._next_btn.connect("clicked", self._on_next)
        btnbar.append(self._next_btn)

        self._show_screen()

    def _show_screen(self):
        child = self._content.get_first_child()
        while child:
            self._content.remove(child)
            child = self._content.get_first_child()

        name = self.SCREENS[self.current]
        self._progress.set_fraction((self.current + 1) / len(self.SCREENS))
        self._back_btn.set_sensitive(self.current > 0)
        self._next_btn.set_label("Launch ClawOS" if name == "complete" else "Continue")

        screen_fn = getattr(self, f"_screen_{name}", self._screen_placeholder)
        widget = screen_fn()
        if widget:
            self._content.append(widget)

    def _make_header(self, title: str, subtitle: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(48)
        box.set_margin_end(48)
        box.set_margin_top(40)
        box.set_margin_bottom(24)

        t = Gtk.Label(label=title)
        t.add_css_class("title-1")
        t.set_halign(Gtk.Align.START)
        box.append(t)

        s = Gtk.Label(label=subtitle)
        s.add_css_class("body")
        s.set_halign(Gtk.Align.START)
        s.set_wrap(True)
        s.set_max_width_chars(60)
        box.append(s)
        return box

    def _screen_welcome(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self._make_header(
            "Welcome to ClawOS",
            "Your private, offline AI workstation. This wizard sets up your environment.\n"
            "Takes about 5 minutes.",
        ))
        lbl = Gtk.Label(label="No API keys. No cloud. No monthly bill.")
        lbl.add_css_class("title-4")
        lbl.set_margin_start(48)
        lbl.set_margin_top(16)
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)
        return box

    def _screen_hardware(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self._make_header("Hardware Detected", "ClawOS detected your hardware profile."))
        try:
            from bootstrap.hardware_probe import probe
            hw = probe()
            ram = hw.get("ram_gb", "?")
            gpu = hw.get("gpu_name", "CPU only")
            tier = hw.get("tier", "B")
            tier_model = {"A": "qwen2.5:1.5b", "B": "qwen2.5:3b", "C": "qwen2.5:7b"}.get(tier, "qwen2.5:7b")
            self.choices["hardware"] = hw
            self.choices["recommended_model"] = tier_model
        except Exception:
            ram, gpu, tier, tier_model = "?", "Unknown", "B", "qwen2.5:7b"
            self.choices["recommended_model"] = tier_model

        grid = Gtk.Grid()
        grid.set_column_spacing(24)
        grid.set_row_spacing(8)
        grid.set_margin_start(48)
        grid.set_margin_top(8)

        for row, (label, value) in enumerate([
            ("RAM", f"{ram} GB"), ("GPU", gpu),
            ("Tier", f"Tier {tier}"), ("Recommended model", tier_model),
        ]):
            lbl = Gtk.Label(label=label)
            lbl.set_halign(Gtk.Align.START)
            lbl.add_css_class("dim-label")
            val = Gtk.Label(label=str(value))
            val.set_halign(Gtk.Align.START)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(val, 1, row, 1, 1)
        box.append(grid)
        return box

    def _screen_edition(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self._make_header("Choose Edition", "Desktop or Server?"))

        grp = Adw.PreferencesGroup()
        grp.set_margin_start(48)
        grp.set_margin_end(48)

        desktop_row = Adw.ActionRow()
        desktop_row.set_title("Desktop")
        desktop_row.set_subtitle("Voice, dashboard, GUI — daily driver workstation")
        desktop_check = Gtk.CheckButton()
        desktop_check.set_active(True)
        desktop_row.add_suffix(desktop_check)
        grp.add(desktop_row)

        server_row = Adw.ActionRow()
        server_row.set_title("Server")
        server_row.set_subtitle("Headless, remote dashboard, SSH — homelab / always-on")
        server_check = Gtk.CheckButton()
        server_check.set_group(desktop_check)
        server_row.add_suffix(server_check)
        grp.add(server_row)

        self.choices["edition"] = "desktop"
        desktop_check.connect("toggled", lambda b: self.choices.update(
            {"edition": "desktop" if b.get_active() else "server"}
        ))
        box.append(grp)
        return box

    def _screen_model(self):
        recommended = self.choices.get("recommended_model", "qwen2.5:7b")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self._make_header("AI Model", f"Recommended for your hardware: {recommended}"))

        grp = Adw.PreferencesGroup()
        grp.set_margin_start(48)
        grp.set_margin_end(48)

        models = [
            ("qwen2.5:1.5b", "Basic — 4GB+ RAM",   "Fast responses, simple Q&A"),
            ("qwen2.5:3b",   "Standard — 6GB+ RAM", "Writing, summarization, general tasks"),
            ("qwen2.5:7b",   "Full — 8GB+ RAM",     "Tools, code, RAG — recommended"),
        ]

        first_btn = None
        for model_id, title, subtitle in models:
            row = Adw.ActionRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            btn = Gtk.CheckButton()
            if first_btn is None:
                first_btn = btn
            else:
                btn.set_group(first_btn)
            btn.set_active(model_id == recommended)
            row.add_suffix(btn)
            btn.connect("toggled", lambda b, m=model_id: b.get_active() and self.choices.update({"model": m}))
            grp.add(row)

        self.choices.setdefault("model", recommended)
        box.append(grp)
        return box

    def _screen_workspace(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self._make_header("Workspace", "Name your default workspace."))
        entry = Gtk.Entry()
        entry.set_text(self.choices.get("workspace", "nexus_default"))
        entry.set_margin_start(48)
        entry.set_margin_end(48)
        entry.set_max_width_chars(40)
        entry.connect("changed", lambda e: self.choices.update({"workspace": e.get_text()}))
        self.choices.setdefault("workspace", "nexus_default")
        box.append(entry)
        return box

    def _screen_voice(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self._make_header("Voice", "Enable voice with wake word detection."))
        grp = Adw.PreferencesGroup()
        grp.set_margin_start(48)
        grp.set_margin_end(48)
        voice_row = Adw.SwitchRow()
        voice_row.set_title("Enable voice pipeline")
        voice_row.set_subtitle("Whisper STT + Piper TTS + 'Hey Nexus' wake word")
        voice_row.set_active(True)
        voice_row.connect("notify::active", lambda r, _: self.choices.update({"voice": r.get_active()}))
        self.choices["voice"] = True
        grp.add(voice_row)
        box.append(grp)
        return box

    def _screen_openclaw(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self._make_header("OpenClaw", "Install OpenClaw for WhatsApp + 13,700+ skills."))
        grp = Adw.PreferencesGroup()
        grp.set_margin_start(48)
        grp.set_margin_end(48)
        oc_row = Adw.SwitchRow()
        oc_row.set_title("Install OpenClaw")
        oc_row.set_subtitle("Adds WhatsApp, 13,700+ community skills, Nexus Command dashboard")
        oc_row.set_active(True)
        oc_row.connect("notify::active", lambda r, _: self.choices.update({"openclaw": r.get_active()}))
        self.choices["openclaw"] = True
        grp.add(oc_row)
        box.append(grp)
        return box

    def _screen_review(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(self._make_header("Review", "Your setup summary. Click Continue to install."))
        grid = Gtk.Grid()
        grid.set_column_spacing(24)
        grid.set_row_spacing(8)
        grid.set_margin_start(48)
        items = [
            ("Edition",   self.choices.get("edition", "desktop")),
            ("Model",     self.choices.get("model", "qwen2.5:7b")),
            ("Workspace", self.choices.get("workspace", "nexus_default")),
            ("Voice",     "Enabled" if self.choices.get("voice") else "Disabled"),
            ("OpenClaw",  "Will install" if self.choices.get("openclaw") else "Skip"),
        ]
        for row, (label, value) in enumerate(items):
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("dim-label")
            lbl.set_halign(Gtk.Align.START)
            val = Gtk.Label(label=str(value))
            val.set_halign(Gtk.Align.START)
            grid.attach(lbl, 0, row, 1, 1)
            grid.attach(val, 1, row, 1, 1)
        box.append(grid)
        return box

    def _screen_install(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.append(self._make_header("Installing", "Setting up ClawOS on your system..."))

        self._install_progress = Gtk.ProgressBar()
        self._install_progress.set_margin_start(48)
        self._install_progress.set_margin_end(48)
        box.append(self._install_progress)

        self._install_log = Gtk.Label(label="Starting...")
        self._install_log.set_margin_start(48)
        self._install_log.add_css_class("dim-label")
        self._install_log.set_halign(Gtk.Align.START)
        box.append(self._install_log)

        self._next_btn.set_sensitive(False)

        def _run():
            steps = [
                ("Running bootstrap...", self._run_bootstrap),
                ("Pulling AI model...",  self._pull_model),
                ("Starting services...", self._start_services),
                ("Finalizing...",        self._finalize),
            ]
            for i, (msg, fn) in enumerate(steps):
                GLib.idle_add(self._install_log.set_label, msg)
                GLib.idle_add(self._install_progress.set_fraction, i / len(steps))
                try:
                    fn()
                except Exception as e:
                    GLib.idle_add(self._install_log.set_label, f"Error: {e}")
            GLib.idle_add(self._install_progress.set_fraction, 1.0)
            GLib.idle_add(self._next_btn.set_sensitive, True)
            GLib.idle_add(self._on_next, None)

        threading.Thread(target=_run, daemon=True).start()
        return box

    def _run_bootstrap(self):
        root = Path(__file__).parent.parent.parent
        subprocess.run(
            [sys.executable, "-m", "bootstrap.bootstrap",
             "--workspace", self.choices.get("workspace", "nexus_default")],
            cwd=str(root), check=True,
        )

    def _pull_model(self):
        model = self.choices.get("model", "qwen2.5:7b")
        subprocess.run(["ollama", "pull", model], check=True)

    def _start_services(self):
        subprocess.run(["systemctl", "--user", "enable", "--now", "clawos.service"])

    def _finalize(self):
        WIZARD_DONE_MARKER.parent.mkdir(parents=True, exist_ok=True)
        WIZARD_DONE_MARKER.touch()

    def _screen_complete(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.append(self._make_header("ClawOS is Ready", "Your AI workstation is set up and running."))
        ws    = self.choices.get("workspace", "nexus_default")
        model = self.choices.get("model", "qwen2.5:7b")
        info  = Gtk.Label(label=f"Workspace: {ws}  ·  Model: {model}\nDashboard: http://localhost:7070")
        info.set_margin_start(48)
        info.set_halign(Gtk.Align.START)
        info.add_css_class("body")
        box.append(info)
        return box

    def _screen_placeholder(self):
        lbl = Gtk.Label(label=f"Screen: {self.SCREENS[self.current]}")
        lbl.set_margin_start(48)
        return lbl

    def _on_next(self, _):
        if self.current < len(self.SCREENS) - 1:
            self.current += 1
            self._show_screen()
        else:
            self.get_application().quit()

    def _on_back(self, _):
        if self.current > 0:
            self.current -= 1
            self._show_screen()


def run_gtk_wizard():
    """Entry point for GTK4 first-run wizard."""
    if WIZARD_DONE_MARKER.exists():
        print("Wizard already completed. Run with --reset to redo.")
        if "--reset" not in sys.argv:
            return
    app = Adw.Application(application_id="io.clawos.Setup")
    app.connect("activate", lambda a: ClawOSSetupWindow(a).present())
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    run_gtk_wizard()
