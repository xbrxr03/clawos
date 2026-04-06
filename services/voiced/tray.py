# SPDX-License-Identifier: AGPL-3.0-or-later
"""
System tray indicator for voice state.
States: sleeping → listening → thinking → speaking
Requires: pystray, Pillow
"""
import threading
from enum import Enum


class VoiceState(Enum):
    SLEEPING  = "sleeping"
    LISTENING = "listening"
    THINKING  = "thinking"
    SPEAKING  = "speaking"


STATE_COLORS = {
    VoiceState.SLEEPING:  (80, 80, 80),
    VoiceState.LISTENING: (48, 209, 88),   # green
    VoiceState.THINKING:  (255, 159, 10),  # amber
    VoiceState.SPEAKING:  (41, 151, 255),  # blue
}


class VoiceTray:
    def __init__(self):
        self._state  = VoiceState.SLEEPING
        self._icon   = None
        self._thread = None

    def start(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            self._pystray    = pystray
            self._Image      = Image
            self._ImageDraw  = ImageDraw
            self._thread     = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        except ImportError:
            pass  # tray unavailable — no-op

    def set_state(self, state: VoiceState):
        self._state = state
        if self._icon:
            self._icon.icon = self._make_icon()

    def _make_icon(self):
        img  = self._Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = self._ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill=STATE_COLORS[self._state])
        return img

    def _run(self):
        menu = self._pystray.Menu(
            self._pystray.MenuItem(
                "Nexus — " + self._state.value, None, enabled=False
            ),
            self._pystray.MenuItem("Quit voice", lambda: self._icon.stop()),
        )
        self._icon = self._pystray.Icon(
            "nexus_voice", self._make_icon(), "Nexus Voice", menu
        )
        self._icon.run()
