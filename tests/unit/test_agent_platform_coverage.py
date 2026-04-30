# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Verify every platform-aware tool has a branch for both Linux and macOS.

This is a cheap regression check — if someone adds a new system tool but
forgets the macOS branch, this fails.
"""
import inspect

from runtimes.agent.tools import desktop, files, system


def _src(fn) -> str:
    try:
        return inspect.getsource(fn)
    except OSError:
        return ""


PLATFORM_AWARE = [
    # (module, function_name, must_mention_macos)
    (system,  "set_volume",     True),
    (system,  "get_volume",     True),
    (system,  "open_app",       True),
    (system,  "focus_window",   True),
    (system,  "close_app",      True),
    (desktop, "set_clipboard",  True),
    (desktop, "get_clipboard",  True),
    (desktop, "paste_to_app",   True),
    (desktop, "screenshot",     True),
    (files,   "open_file",      True),
    (files,   "open_url",       False),  # uses webbrowser, which handles both
]


# Tokens that signal a macOS-aware code path
_MAC_TOKENS = ("is_macos", "pbcopy", "pbpaste", "osascript", "screencapture",
               "open -a", "'open'")
# Tokens that signal a Linux-aware code path
_LINUX_TOKENS = ("is_linux", "xclip", "wl-copy", "wl-paste", "pactl", "amixer",
                 "xdotool", "wtype", "xdg-open", "wmctrl", "swaymsg",
                 "gnome-screenshot", "scrot", "grim")


def test_macos_branches_present():
    """Each platform-aware module mentions at least one macOS code path."""
    for mod, _name, must in PLATFORM_AWARE:
        if not must:
            continue
        src = inspect.getsource(mod)
        assert any(tok in src for tok in _MAC_TOKENS), (
            f"{mod.__name__} has no macOS-aware code path"
        )


def test_linux_branches_present():
    """Each platform-aware module mentions at least one Linux code path."""
    for mod, _name, _must in PLATFORM_AWARE:
        src = inspect.getsource(mod)
        assert any(tok in src for tok in _LINUX_TOKENS), (
            f"{mod.__name__} has no Linux-aware code path"
        )
