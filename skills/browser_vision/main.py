# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Browser Automation 2.0 - Vision-Based Control
==============================================
Modern browser automation using vision models and accessibility trees.

Features:
- Vision-based element detection (screenshot → action)
- Accessibility tree parsing for reliable selectors
- Multi-agent browser workflows
- Action caching for common tasks
- Chrome extension integration

Addresses the browser automation gap from CRITICAL_GAPS_RESEARCH.md
"""
import asyncio
import base64
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from clawos_core.constants import CLAWOS_DIR

log = logging.getLogger("browser_vision")

# Database for action caching
BROWSER_CACHE_DB = CLAWOS_DIR / "browser_cache.db"


class ActionType(Enum):
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    NAVIGATE = "navigate"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"


@dataclass
class BrowserAction:
    """A browser action with vision-based targeting."""
    type: ActionType
    target: Optional[str] = None  # Element description or selector
    value: Optional[str] = None  # Text to type, URL to navigate, etc.
    coordinates: Optional[Tuple[int, int]] = None  # x, y for vision-based
    confidence: float = 0.0  # Vision model confidence
    reasoning: Optional[str] = None  # Why this action was chosen


@dataclass
class ActionResult:
    """Result of executing a browser action."""
    success: bool
    screenshot: Optional[bytes] = None
    extracted_text: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class VisionElementDetector:
    """
    Detect UI elements using vision models.
    
    Uses screenshot + LLM vision to identify clickable elements,
    form fields, and interactive components.
    """
    
    def __init__(self, model_endpoint: str = "http://localhost:11434"):
        self.model_endpoint = model_endpoint
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def detect_elements(
        self,
        screenshot: bytes,
        instruction: str
    ) -> List[Dict[str, Any]]:
        """
        Detect UI elements matching the instruction.
        
        Returns list of elements with:
        - description: what the element is
        - coordinates: (x, y) center point
        - confidence: detection confidence
        - action: suggested action (click, type, etc.)
        """
        try:
            # Encode screenshot
            img_b64 = base64.b64encode(screenshot).decode()
            
            # Build prompt for vision model
            prompt = f"""Analyze this webpage screenshot and identify elements needed to: {instruction}

Return a JSON array of interactive elements found:
[
  {{
    "description": "what the element is (e.g., 'Search button', 'Email input field')",
    "coordinates": [x, y],
    "confidence": 0.95,
    "action": "click|type|scroll",
    "selector_hint": "accessibility selector if visible"
  }}
]

Only include elements directly relevant to the task. Be precise with coordinates."""

            # Call vision-capable model (e.g., llava, bakllava via Ollama)
            response = await self.client.post(
                f"{self.model_endpoint}/api/generate",
                json={
                    "model": "bakllava:latest",  # Vision-capable model
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False,
                    "format": "json"
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            try:
                elements = json.loads(data.get("response", "[]"))
                if not isinstance(elements, list):
                    elements = [elements]
                return elements
            except json.JSONDecodeError:
                # Try to extract JSON from text
                text = data.get("response", "")
                # Find JSON array in text
                start = text.find("[")
                end = text.rfind("]")
                if start >= 0 and end > start:
                    elements = json.loads(text[start:end+1])
                    return elements if isinstance(elements, list) else [elements]
                return []
        
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"Vision detection failed: {e}")
            return []
    
    async def decide_action(
        self,
        screenshot: bytes,
        goal: str,
        previous_actions: List[BrowserAction]
    ) -> BrowserAction:
        """
        Decide the next action based on current state and goal.
        
        Uses vision model to understand the page and choose the best action.
        """
        try:
            img_b64 = base64.b64encode(screenshot).decode()
            
            # Build context from previous actions
            history = "\n".join([
                f"- {a.type.value}: {a.target or a.value}"
                for a in previous_actions[-5:]  # Last 5 actions
            ])
            
            prompt = f"""You are controlling a web browser. Current goal: {goal}

Previous actions:
{history if history else "None"}

Based on the current screenshot, what is the SINGLE next action to take?

Return JSON:
{{
  "action": "click|type|scroll|navigate|wait|extract",
  "target": "description of element to interact with",
  "value": "text to type or URL to navigate to (if applicable)",
  "coordinates": [x, y],
  "reasoning": "why this action was chosen"
}}

Choose the most logical next step toward the goal."""

            response = await self.client.post(
                f"{self.model_endpoint}/api/generate",
                json={
                    "model": "bakllava:latest",
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False,
                    "format": "json"
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parse decision
            try:
                decision = json.loads(data.get("response", "{}"))
            except json.JSONDecodeError:
                text = data.get("response", "")
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    decision = json.loads(text[start:end+1])
                else:
                    decision = {}
            
            action_type = ActionType(decision.get("action", "wait"))
            coords = decision.get("coordinates", [0, 0])
            
            return BrowserAction(
                type=action_type,
                target=decision.get("target"),
                value=decision.get("value"),
                coordinates=(coords[0], coords[1]) if isinstance(coords, list) and len(coords) >= 2 else None,
                reasoning=decision.get("reasoning")
            )
        
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"Action decision failed: {e}")
            return BrowserAction(
                type=ActionType.WAIT,
                reasoning=f"Error: {str(e)}"
            )


class AccessibilityTreeParser:
    """
    Parse browser accessibility tree for reliable element selection.
    
    More reliable than CSS selectors for automation.
    """
    
    async def get_accessibility_tree(self, page: Page) -> Dict[str, Any]:
        """Get accessibility tree from page."""
        # Use Chrome DevTools Protocol to get accessibility tree
        client = await page.context.new_cdp_session(page)
        
        result = await client.send("Accessibility.getFullAXTree")
        return result.get("nodes", [])
    
    def find_element(
        self,
        tree: List[Dict],
        criteria: Dict[str, Any]
    ) -> Optional[Dict]:
        """
        Find element in accessibility tree matching criteria.
        
        Criteria can include:
        - role: button, link, textbox, etc.
        - name: accessible name/label
        - description: additional description
        """
        for node in tree:
            match = True
            for key, value in criteria.items():
                if node.get(key) != value:
                    match = False
                    break
            
            if match:
                return node
            
            # Search children
            if "children" in node:
                child_match = self.find_element(node["children"], criteria)
                if child_match:
                    return child_match
        
        return None


class ActionCache:
    """
    Cache successful action sequences for replay.
    
    Enables deterministic replay without LLM calls for common tasks.
    """
    
    def __init__(self, db_path: Path = BROWSER_CACHE_DB):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize cache database."""
        BROWSER_CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS action_sequences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_hash TEXT UNIQUE NOT NULL,
                    domain TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    actions TEXT NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    last_used REAL NOT NULL
                )
            """)
            conn.commit()
    
    def _hash_task(self, domain: str, task: str) -> str:
        """Create hash for task lookup."""
        import hashlib
        return hashlib.md5(f"{domain}:{task}".encode()).hexdigest()
    
    def get_cached_sequence(
        self,
        domain: str,
        task: str
    ) -> Optional[List[BrowserAction]]:
        """Get cached action sequence if available."""
        task_hash = self._hash_task(domain, task)
        
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT actions, success_count, fail_count
                   FROM action_sequences
                   WHERE task_hash = ? AND success_count > fail_count""",
                (task_hash,)
            ).fetchone()
            
            if row:
                actions_data = json.loads(row[0])
                actions = [
                    BrowserAction(
                        type=ActionType(a["type"]),
                        target=a.get("target"),
                        value=a.get("value"),
                        coordinates=a.get("coordinates")
                    )
                    for a in actions_data
                ]
                
                # Update last_used
                conn.execute(
                    "UPDATE action_sequences SET last_used = ? WHERE task_hash = ?",
                    (time.time(), task_hash)
                )
                conn.commit()
                
                log.info(f"Using cached action sequence for {domain}: {task}")
                return actions
            
            return None
    
    def cache_sequence(
        self,
        domain: str,
        task: str,
        actions: List[BrowserAction],
        success: bool
    ):
        """Cache or update action sequence."""
        task_hash = self._hash_task(domain, task)
        
        actions_data = [
            {
                "type": a.type.value,
                "target": a.target,
                "value": a.value,
                "coordinates": a.coordinates
            }
            for a in actions
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            # Check if exists
            existing = conn.execute(
                "SELECT success_count, fail_count FROM action_sequences WHERE task_hash = ?",
                (task_hash,)
            ).fetchone()
            
            if existing:
                # Update counts
                if success:
                    conn.execute(
                        "UPDATE action_sequences SET success_count = success_count + 1, last_used = ? WHERE task_hash = ?",
                        (time.time(), task_hash)
                    )
                else:
                    conn.execute(
                        "UPDATE action_sequences SET fail_count = fail_count + 1 WHERE task_hash = ?",
                        (task_hash,)
                    )
            else:
                # Insert new
                conn.execute(
                    """INSERT INTO action_sequences
                       (task_hash, domain, task_description, actions, success_count, fail_count, created_at, last_used)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (task_hash, domain, task, json.dumps(actions_data),
                     1 if success else 0, 0 if success else 1,
                     time.time(), time.time())
                )
            
            conn.commit()


class VisionBrowserAgent:
    """
    Browser automation agent using vision and accessibility.
    
    Combines:
    - Vision-based element detection
    - Accessibility tree parsing
    - Action caching
    - Multi-step task execution
    """
    
    def __init__(
        self,
        headless: bool = False,
        use_cache: bool = True,
        model_endpoint: str = "http://localhost:11434"
    ):
        self.headless = headless
        self.use_cache = use_cache
        self.vision = VisionElementDetector(model_endpoint)
        self.accessibility = AccessibilityTreeParser()
        self.cache = ActionCache() if use_cache else None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def start(self):
        """Start browser session."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.0"
        )
        self.page = await self.context.new_page()
        log.info("Browser session started")
    
    async def stop(self):
        """Stop browser session."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        log.info("Browser session stopped")
    
    async def execute_task(
        self,
        goal: str,
        max_steps: int = 20,
        start_url: Optional[str] = None
    ) -> ActionResult:
        """
        Execute a browser task using vision-based automation.
        
        Args:
            goal: Natural language description of the task
            max_steps: Maximum number of actions to take
            start_url: Optional URL to start at
        
        Returns:
            ActionResult with success status and final state
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        # Navigate to starting URL if provided
        if start_url:
            await self.page.goto(start_url)
            await asyncio.sleep(1)
        
        # Get domain for caching
        current_url = self.page.url
        domain = urlparse(current_url).netloc
        
        # Check cache
        if self.cache:
            cached_actions = self.cache.get_cached_sequence(domain, goal)
            if cached_actions:
                return await self._execute_cached_sequence(cached_actions)
        
        # Execute with vision-based decision making
        actions_taken: List[BrowserAction] = []
        
        for step in range(max_steps):
            # Take screenshot
            screenshot = await self.page.screenshot()
            
            # Decide next action
            action = await self.vision.decide_action(screenshot, goal, actions_taken)
            
            log.info(f"Step {step + 1}: {action.type.value} - {action.reasoning}")
            
            # Execute action
            result = await self._execute_action(action)
            actions_taken.append(action)
            
            if not result.success:
                # Cache failure
                if self.cache:
                    self.cache.cache_sequence(domain, goal, actions_taken, False)
                return ActionResult(
                    success=False,
                    error=result.error,
                    screenshot=result.screenshot
                )
            
            # Check if goal is achieved
            if await self._check_goal_achieved(goal):
                # Cache success
                if self.cache:
                    self.cache.cache_sequence(domain, goal, actions_taken, True)
                
                final_screenshot = await self.page.screenshot()
                return ActionResult(
                    success=True,
                    screenshot=final_screenshot
                )
            
            await asyncio.sleep(0.5)  # Brief pause between actions
        
        # Max steps reached
        return ActionResult(
            success=False,
            error=f"Max steps ({max_steps}) reached without achieving goal",
            screenshot=await self.page.screenshot()
        )
    
    async def _execute_action(self, action: BrowserAction) -> ActionResult:
        """Execute a single browser action."""
        start_time = time.time()
        
        try:
            if action.type == ActionType.CLICK:
                if action.coordinates:
                    await self.page.mouse.click(action.coordinates[0], action.coordinates[1])
                elif action.target:
                    await self.page.click(f"text={action.target}")
            
            elif action.type == ActionType.TYPE:
                if action.target and action.value:
                    await self.page.fill(f"text={action.target}", action.value)
                elif action.value:
                    await self.page.keyboard.type(action.value)
            
            elif action.type == ActionType.NAVIGATE:
                if action.value:
                    await self.page.goto(action.value)
            
            elif action.type == ActionType.SCROLL:
                await self.page.evaluate("window.scrollBy(0, 300)")
            
            elif action.type == ActionType.WAIT:
                await asyncio.sleep(2)
            
            elif action.type == ActionType.SCREENSHOT:
                screenshot = await self.page.screenshot()
                return ActionResult(success=True, screenshot=screenshot)
            
            elif action.type == ActionType.EXTRACT:
                text = await self.page.evaluate("document.body.innerText")
                return ActionResult(success=True, extracted_text=text)
            
            duration = (time.time() - start_time) * 1000
            return ActionResult(success=True, duration_ms=duration)
        
        except (OSError, RuntimeError, TimeoutError) as e:
            duration = (time.time() - start_time) * 1000
            return ActionResult(
                success=False,
                error=str(e),
                duration_ms=duration
            )
    
    async def _execute_cached_sequence(
        self,
        actions: List[BrowserAction]
    ) -> ActionResult:
        """Execute a cached action sequence."""
        for i, action in enumerate(actions):
            result = await self._execute_action(action)
            
            if not result.success:
                log.warning(f"Cached action {i+1} failed: {result.error}")
                # Fall back to vision-based
                return await self.execute_task(
                    action.target or "continue task",
                    max_steps=10
                )
        
        return ActionResult(
            success=True,
            screenshot=await self.page.screenshot()
        )
    
    async def _check_goal_achieved(self, goal: str) -> bool:
        """Check if the goal has been achieved."""
        # Take screenshot and ask vision model
        screenshot = await self.page.screenshot()
        img_b64 = base64.b64encode(screenshot).decode()
        
        try:
            response = await self.vision.client.post(
                f"{self.vision.model_endpoint}/api/generate",
                json={
                    "model": "bakllava:latest",
                    "prompt": f"Goal: {goal}\n\nHas this goal been achieved based on the current webpage? Answer only 'yes' or 'no'.",
                    "images": [img_b64],
                    "stream": False
                }
            )
            
            response.raise_for_status()
            data = response.json()
            answer = data.get("response", "").lower().strip()
            
            return "yes" in answer and "no" not in answer
        
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"Goal check failed: {e}")
            return False


# Convenience functions

async def run_browser_task(
    goal: str,
    start_url: Optional[str] = None,
    headless: bool = False,
    max_steps: int = 20
) -> ActionResult:
    """Run a browser task with vision-based automation."""
    agent = VisionBrowserAgent(headless=headless)
    
    try:
        await agent.start()
        result = await agent.execute_task(goal, max_steps, start_url)
        return result
    finally:
        await agent.stop()
