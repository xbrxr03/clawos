# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Desktop Automation Service (desktopd)
======================================
Computer control via screenshot, vision, and input automation.

Features:
- Screenshot capture
- PyAutoGUI/pynput input control
- Vision-based UI understanding
- Mouse, keyboard, clipboard control
- Safety policies (what can/cannot be automated)
- Multi-platform (Linux, macOS, Windows)

Addresses the Desktop Computer Use gap from CRITICAL_GAPS_RESEARCH.md
"""
import asyncio
import base64
import io
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
import uvicorn

# Platform detection
import sys
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

# Try to import automation libraries
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import pynput
    from pynput.mouse import Button
    from pynput.keyboard import Key
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    import PIL.Image
    import PIL.ImageGrab
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    from Xlib import display
    XLIB_AVAILABLE = True
except ImportError:
    XLIB_AVAILABLE = False

from clawos_core.constants import CLAWOS_DIR, PORT_DESKTOPD

log = logging.getLogger("desktopd")

# Safety policy
class SafetyLevel(Enum):
    DENY = "deny"       # Block action
    ASK = "ask"         # Require approval
    ALLOW = "allow"     # Permit action


class ActionType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    DRAG = "drag"
    SCROLL = "scroll"
    TYPE = "type"
    HOTKEY = "hotkey"
    SCREENSHOT = "screenshot"
    CLIPBOARD_GET = "clipboard_get"
    CLIPBOARD_SET = "clipboard_set"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    GET_CURSOR_POS = "get_cursor_pos"
    MOVE_TO = "move_to"


@dataclass
class SafetyPolicy:
    """Safety policy for desktop automation."""
    allow_screenshots: bool = True
    allow_mouse: bool = True
    allow_keyboard: bool = True
    allow_clipboard: bool = True
    
    # Restricted zones (areas that cannot be clicked)
    restricted_zones: List[Tuple[int, int, int, int]] = None  # x, y, w, h
    
    # Require approval for these actions
    require_approval: List[ActionType] = None
    
    def __post_init__(self):
        if self.restricted_zones is None:
            self.restricted_zones = []
        if self.require_approval is None:
            self.require_approval = []


@dataclass
class DesktopAction:
    """A desktop automation action."""
    type: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    keys: Optional[List[str]] = None
    button: str = "left"  # left, right, middle
    duration: float = 0.25  # seconds for movement
    clicks: int = 1
    dx: int = 0  # scroll amount
    dy: int = 0


class ScreenshotCapture:
    """
    Cross-platform screenshot capture.
    
    Supports multiple backends:
    - PIL ImageGrab (cross-platform)
    - X11 (Linux)
    - Quartz (macOS)
    """
    
    def __init__(self):
        self.backend = self._detect_backend()
        log.info(f"Screenshot backend: {self.backend}")
    
    def _detect_backend(self) -> str:
        """Detect best screenshot backend."""
        if PILLOW_AVAILABLE:
            return "pillow"
        elif XLIB_AVAILABLE and IS_LINUX:
            return "x11"
        else:
            return "none"
    
    def capture(self, region: Optional[Tuple[int, int, int, int]] = None) -> bytes:
        """
        Capture screenshot.
        
        Args:
            region: Optional (x, y, w, h) to capture specific area
        
        Returns:
            PNG image bytes
        """
        if self.backend == "pillow":
            return self._capture_pillow(region)
        elif self.backend == "x11":
            return self._capture_x11(region)
        else:
            raise RuntimeError("No screenshot backend available")
    
    def _capture_pillow(self, region: Optional[Tuple[int, int, int, int]]) -> bytes:
        """Capture using PIL."""
        screenshot = PIL.ImageGrab.grab(bbox=region)
        
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        return buffer.getvalue()
    
    def _capture_x11(self, region: Optional[Tuple[int, int, int, int]]) -> bytes:
        """Capture using X11."""
        display_obj = display.Display()
        root = display_obj.screen().root
        
        if region:
            x, y, w, h = region
            raw = root.get_image(x, y, w, h, Xlib.X.ZPixmap, 0xffffffff)
        else:
            width = root.get_geometry().width
            height = root.get_geometry().height
            raw = root.get_image(0, 0, width, height, Xlib.X.ZPixmap, 0xffffffff)
        
        # Convert to PIL Image
        screenshot = PIL.Image.frombytes(
            "RGB",
            (region[2] if region else width, region[3] if region else height),
            raw.data,
            "raw",
            "BGRX"
        )
        
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        return buffer.getvalue()
    
    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen dimensions."""
        if PYAUTOGUI_AVAILABLE:
            return pyautogui.size()
        elif self.backend == "pillow":
            screenshot = PIL.ImageGrab.grab()
            return screenshot.size
        else:
            return (1920, 1080)  # Default


class InputController:
    """
    Cross-platform input automation.
    
    Supports:
    - pyautogui (preferred)
    - pynput (fallback)
    """
    
    def __init__(self):
        self.backend = self._detect_backend()
        log.info(f"Input backend: {self.backend}")
        
        if self.backend == "pynput":
            self.mouse = pynput.mouse.Controller()
            self.keyboard = pynput.keyboard.Controller()
    
    def _detect_backend(self) -> str:
        """Detect best input backend."""
        if PYAUTOGUI_AVAILABLE:
            # Configure pyautogui
            pyautogui.FAILSAFE = True  # Move to corner to abort
            pyautogui.PAUSE = 0.1
            return "pyautogui"
        elif PYNPUT_AVAILABLE:
            return "pynput"
        else:
            return "none"
    
    def move_to(self, x: int, y: int, duration: float = 0.25):
        """Move mouse to position."""
        if self.backend == "pyautogui":
            pyautogui.moveTo(x, y, duration=duration)
        elif self.backend == "pynput":
            self.mouse.position = (x, y)
            time.sleep(duration)
    
    def click(self, x: Optional[int] = None, y: Optional[int] = None,
              button: str = "left", clicks: int = 1):
        """Click mouse at position."""
        if x is not None and y is not None:
            self.move_to(x, y)
        
        button_map = {
            "left": pyautogui.PRIMARY if self.backend == "pyautogui" else Button.left,
            "right": pyautogui.SECONDARY if self.backend == "pyautogui" else Button.right,
            "middle": pyautogui.MIDDLE if self.backend == "pyautogui" else Button.middle
        }
        
        btn = button_map.get(button, button_map["left"])
        
        if self.backend == "pyautogui":
            pyautogui.click(button=btn, clicks=clicks)
        elif self.backend == "pynput":
            for _ in range(clicks):
                self.mouse.press(btn)
                self.mouse.release(btn)
                time.sleep(0.05)
    
    def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Double-click mouse."""
        self.click(x, y, clicks=2)
    
    def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Right-click mouse."""
        self.click(x, y, button="right")
    
    def drag_to(self, x: int, y: int, duration: float = 0.5):
        """Drag to position."""
        if self.backend == "pyautogui":
            pyautogui.dragTo(x, y, duration=duration)
        elif self.backend == "pynput":
            self.mouse.press(Button.left)
            self.move_to(x, y, duration)
            self.mouse.release(Button.left)
    
    def scroll(self, dx: int = 0, dy: int = 0, x: Optional[int] = None, y: Optional[int] = None):
        """Scroll at position."""
        if x is not None and y is not None:
            self.move_to(x, y)
        
        if self.backend == "pyautogui":
            pyautogui.scroll(dy, dx)
        elif self.backend == "pynput":
            self.mouse.scroll(dx, dy)
    
    def type_text(self, text: str, interval: float = 0.01):
        """Type text."""
        if self.backend == "pyautogui":
            pyautogui.typewrite(text, interval=interval)
        elif self.backend == "pynput":
            self.keyboard.type(text)
            time.sleep(interval * len(text))
    
    def press_key(self, key: str):
        """Press a key."""
        if self.backend == "pyautogui":
            pyautogui.press(key)
        elif self.backend == "pynput":
            # Map common keys
            key_map = {
                'enter': Key.enter,
                'esc': Key.esc,
                'tab': Key.tab,
                'space': Key.space,
                'backspace': Key.backspace,
                'delete': Key.delete,
                'home': Key.home,
                'end': Key.end,
                'pageup': Key.page_up,
                'pagedown': Key.page_down,
                'up': Key.up,
                'down': Key.down,
                'left': Key.left,
                'right': Key.right,
                'f1': Key.f1,
                'f2': Key.f2,
                'f3': Key.f3,
                'f4': Key.f4,
                'f5': Key.f5,
                'f6': Key.f6,
                'f7': Key.f7,
                'f8': Key.f8,
                'f9': Key.f9,
                'f10': Key.f10,
                'f11': Key.f11,
                'f12': Key.f12,
            }
            k = key_map.get(key.lower(), key)
            self.keyboard.press(k)
            self.keyboard.release(k)
    
    def hotkey(self, *keys: str):
        """Press hotkey combination."""
        if self.backend == "pyautogui":
            pyautogui.hotkey(*keys)
        elif self.backend == "pynput":
            # Map keys
            key_map = {
                'ctrl': Key.ctrl,
                'alt': Key.alt,
                'shift': Key.shift,
                'cmd': Key.cmd,
                'win': Key.cmd,
                'enter': Key.enter,
                'esc': Key.esc,
                'tab': Key.tab,
                'c': 'c',
                'v': 'v',
                'a': 'a',
                'x': 'x',
                'z': 'z',
                'y': 'y',
                'f': 'f',
                'p': 'p',
                's': 's',
                'n': 'n',
                'o': 'o',
                't': 't',
                'w': 'w',
            }
            
            # Press all keys
            pressed = []
            for key in keys:
                k = key_map.get(key.lower(), key)
                self.keyboard.press(k)
                pressed.append(k)
            
            # Release all keys (reverse order)
            for k in reversed(pressed):
                self.keyboard.release(k)
    
    def get_cursor_pos(self) -> Tuple[int, int]:
        """Get current cursor position."""
        if self.backend == "pyautogui":
            return pyautogui.position()
        elif self.backend == "pynput":
            return self.mouse.position
        return (0, 0)


class ClipboardManager:
    """
    Cross-platform clipboard access.
    """
    
    def __init__(self):
        self.backend = self._detect_backend()
    
    def _detect_backend(self) -> str:
        """Detect best clipboard backend."""
        try:
            import pyperclip
            return "pyperclip"
        except ImportError as e:
            log.debug(f"suppressed: {e}")
        
        if IS_LINUX:
            try:
                import subprocess
                subprocess.run(["xclip", "-version"], capture_output=True)
                return "xclip"
            except (ImportError, OSError) as e:
                log.debug(f"suppressed: {e}")
        
        return "none"
    
    def get(self) -> str:
        """Get clipboard content."""
        if self.backend == "pyperclip":
            import pyperclip
            return pyperclip.paste()
        elif self.backend == "xclip":
            import subprocess
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True
            )
            return result.stdout
        else:
            raise RuntimeError("No clipboard backend available")
    
    def set(self, text: str):
        """Set clipboard content."""
        if self.backend == "pyperclip":
            import pyperclip
            pyperclip.copy(text)
        elif self.backend == "xclip":
            import subprocess
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(),
                capture_output=True
            )
        else:
            raise RuntimeError("No clipboard backend available")


class SafetyEnforcer:
    """
    Enforce safety policies for desktop automation.
    
    Prevents:
    - Clicking in restricted zones
    - Actions requiring approval
    - Dangerous operations
    """
    
    def __init__(self, policy: SafetyPolicy):
        self.policy = policy
    
    def check_action(self, action: DesktopAction) -> Tuple[bool, Optional[str]]:
        """
        Check if action is allowed.
        
        Returns:
            (allowed, reason_if_denied)
        """
        # Check action type restrictions
        if action.type == ActionType.SCREENSHOT and not self.policy.allow_screenshots:
            return False, "Screenshots not allowed"
        
        if action.type in [ActionType.CLICK, ActionType.DOUBLE_CLICK,
                          ActionType.RIGHT_CLICK, ActionType.DRAG, ActionType.MOVE_TO]:
            if not self.policy.allow_mouse:
                return False, "Mouse automation not allowed"
        
        if action.type in [ActionType.TYPE, ActionType.HOTKEY, ActionType.KEY_DOWN,
                          ActionType.KEY_UP]:
            if not self.policy.allow_keyboard:
                return False, "Keyboard automation not allowed"
        
        if action.type in [ActionType.CLIPBOARD_GET, ActionType.CLIPBOARD_SET]:
            if not self.policy.allow_clipboard:
                return False, "Clipboard access not allowed"
        
        # Check restricted zones for mouse actions
        if action.x is not None and action.y is not None:
            for zone in self.policy.restricted_zones:
                zx, zy, zw, zh = zone
                if zx <= action.x <= zx + zw and zy <= action.y <= zy + zh:
                    return False, f"Position ({action.x}, {action.y}) is in restricted zone"
        
        # Check if approval required
        if action.type in self.policy.require_approval:
            return False, f"Action {action.type.value} requires approval"
        
        return True, None


class VisionUIAnalyzer:
    """
    Analyze UI using vision models.
    
    Takes screenshots and uses vision models to:
    - Identify UI elements
    - Understand current state
    - Decide next actions
    """
    
    def __init__(self, model_endpoint: str = "http://localhost:11434"):
        self.model_endpoint = model_endpoint
    
    async def analyze_screenshot(self, screenshot: bytes, instruction: str) -> Dict[str, Any]:
        """
        Analyze screenshot for UI understanding.
        
        Returns:
            Dict with elements, suggested actions, etc.
        """
        import httpx
        
        try:
            img_b64 = base64.b64encode(screenshot).decode()
            
            prompt = f"""Analyze this desktop screenshot to: {instruction}

Identify:
1. What application/window is active
2. UI elements visible (buttons, menus, text fields)
3. Current state (what the user is doing)

Return JSON:
{{
    "application": "name of active app",
    "elements": [
        {{"type": "button", "label": "Submit", "location": [x, y]}},
        {{"type": "text_field", "placeholder": "Search...", "location": [x, y]}}
    ],
    "current_state": "description of what's happening",
    "suggested_action": "what to do next"
}}"""

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.model_endpoint}/api/generate",
                    json={
                        "model": "bakllava:latest",
                        "prompt": prompt,
                        "images": [img_b64],
                        "stream": False,
                        "format": "json"
                    },
                    timeout=30.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                try:
                    return json.loads(data.get("response", "{}"))
                except:
                    return {"raw": data.get("response", "")}
        
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"Vision analysis failed: {e}")
            return {"error": str(e)}


class DesktopAutomation:
    """
    Main desktop automation interface.
    
    Combines screenshot, input, clipboard, and safety.
    """
    
    def __init__(self, policy: Optional[SafetyPolicy] = None):
        self.screenshot = ScreenshotCapture()
        self.input = InputController()
        self.clipboard = ClipboardManager()
        self.policy = policy or SafetyPolicy()
        self.safety = SafetyEnforcer(self.policy)
        self.vision = VisionUIAnalyzer()
        
        self._action_history: List[Dict] = []
    
    def execute_action(self, action: DesktopAction) -> Dict[str, Any]:
        """
        Execute a desktop action with safety checks.
        
        Returns:
            Result dict with success status
        """
        # Safety check
        allowed, reason = self.safety.check_action(action)
        if not allowed:
            return {
                "success": False,
                "error": reason,
                "action": action.type.value
            }
        
        start_time = time.time()
        
        try:
            if action.type == ActionType.SCREENSHOT:
                img = self.screenshot.capture()
                return {
                    "success": True,
                    "image": base64.b64encode(img).decode(),
                    "size": len(img)
                }
            
            elif action.type == ActionType.MOVE_TO:
                self.input.move_to(action.x, action.y, action.duration)
                return {"success": True}
            
            elif action.type == ActionType.CLICK:
                self.input.click(action.x, action.y, action.button, action.clicks)
                return {"success": True}
            
            elif action.type == ActionType.DOUBLE_CLICK:
                self.input.double_click(action.x, action.y)
                return {"success": True}
            
            elif action.type == ActionType.RIGHT_CLICK:
                self.input.right_click(action.x, action.y)
                return {"success": True}
            
            elif action.type == ActionType.DRAG:
                self.input.drag_to(action.x, action.y, action.duration)
                return {"success": True}
            
            elif action.type == ActionType.SCROLL:
                self.input.scroll(action.dx, action.dy, action.x, action.y)
                return {"success": True}
            
            elif action.type == ActionType.TYPE:
                self.input.type_text(action.text)
                return {"success": True, "typed": action.text}
            
            elif action.type == ActionType.HOTKEY:
                self.input.hotkey(*action.keys)
                return {"success": True, "keys": action.keys}
            
            elif action.type == ActionType.CLIPBOARD_GET:
                content = self.clipboard.get()
                return {"success": True, "content": content}
            
            elif action.type == ActionType.CLIPBOARD_SET:
                self.clipboard.set(action.text)
                return {"success": True}
            
            elif action.type == ActionType.GET_CURSOR_POS:
                pos = self.input.get_cursor_pos()
                return {"success": True, "position": {"x": pos[0], "y": pos[1]}}
            
            else:
                return {"success": False, "error": f"Unknown action type: {action.type}"}
        
        except (json.JSONDecodeError, ValueError) as e:
            return {
                "success": False,
                "error": str(e),
                "action": action.type.value
            }
    
    async def execute_task(self, instruction: str, max_steps: int = 20) -> Dict[str, Any]:
        """
        Execute a complex task using vision-guided automation.
        
        Args:
            instruction: Natural language instruction
            max_steps: Maximum number of steps
        
        Returns:
            Result with success status and action log
        """
        actions_taken = []
        
        for step in range(max_steps):
            # Screenshot
            screenshot = self.screenshot.capture()
            
            # Analyze with vision
            analysis = await self.vision.analyze_screenshot(screenshot, instruction)
            
            # Check if done
            if "done" in analysis.get("suggested_action", "").lower():
                return {
                    "success": True,
                    "actions": actions_taken,
                    "steps": step + 1
                }
            
            # Execute suggested action (in real implementation, would parse from analysis)
            # For now, just log
            actions_taken.append({
                "step": step + 1,
                "analysis": analysis
            })
        
        return {
            "success": False,
            "error": f"Max steps ({max_steps}) reached",
            "actions": actions_taken
        }


# FastAPI App
app = FastAPI(title="ClawOS Desktop Automation Service", version="0.1.0")

# Global automation instance
automation: Optional[DesktopAutomation] = None


@app.on_event("startup")
async def startup():
    """Initialize desktop automation."""
    global automation
    
    policy = SafetyPolicy(
        allow_screenshots=True,
        allow_mouse=True,
        allow_keyboard=True,
        allow_clipboard=True
    )
    
    automation = DesktopAutomation(policy)
    log.info("Desktop automation service started")


@app.post("/api/v1/screenshot")
async def take_screenshot(region: Optional[List[int]] = None):
    """Take a screenshot."""
    if not automation:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    region_tuple = tuple(region) if region else None
    img = automation.screenshot.capture(region_tuple)
    
    return Response(content=img, media_type="image/png")


@app.post("/api/v1/action")
async def execute_action(action_data: Dict):
    """Execute a desktop action."""
    if not automation:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    action = DesktopAction(
        type=ActionType(action_data.get("type", "screenshot")),
        x=action_data.get("x"),
        y=action_data.get("y"),
        text=action_data.get("text"),
        keys=action_data.get("keys"),
        button=action_data.get("button", "left"),
        duration=action_data.get("duration", 0.25),
        clicks=action_data.get("clicks", 1),
        dx=action_data.get("dx", 0),
        dy=action_data.get("dy", 0)
    )
    
    result = automation.execute_action(action)
    return result


@app.post("/api/v1/task")
async def execute_task(task_data: Dict):
    """Execute a complex task using vision."""
    if not automation:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    instruction = task_data.get("instruction", "")
    max_steps = task_data.get("max_steps", 20)
    
    result = await automation.execute_task(instruction, max_steps)
    return result


@app.get("/api/v1/cursor")
async def get_cursor_position():
    """Get current cursor position."""
    if not automation:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    pos = automation.input.get_cursor_pos()
    return {"x": pos[0], "y": pos[1]}


@app.get("/api/v1/screen")
async def get_screen_info():
    """Get screen dimensions."""
    if not automation:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    size = automation.screenshot.get_screen_size()
    return {"width": size[0], "height": size[1]}


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "up",
        "service": "desktopd",
        "features": {
            "screenshot": PILLOW_AVAILABLE or XLIB_AVAILABLE,
            "mouse": PYAUTOGUI_AVAILABLE or PYNPUT_AVAILABLE,
            "keyboard": PYAUTOGUI_AVAILABLE or PYNPUT_AVAILABLE,
            "clipboard": True
        },
        "platform": sys.platform
    }


def run():
    """Run the desktop automation service."""
def run():
    """Run the desktop automation service."""
    from clawos_core.config.loader import load as load_config
    config = load_config()
    host = config.get("desktop", {}).get("host", "127.0.0.1")
    port = config.get("desktop", {}).get("port", PORT_DESKTOPD)
    
    log.info(f"Starting Desktop Automation service on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
