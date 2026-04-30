#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Essay to Editor Demo
====================

Demonstrates the ClawOS clipboard-aware editing workflow:
1. Copy text from any editor
2. Run this script (or voice command "claw, fix my essay")
3. Grammar check → Rewrite with style → Paste back

Usage:
    python3 demos/essay_to_editor.py [--style formal|casual|academic]

Or via Nexus:
    user: "Fix the grammar in my clipboard"
    nexus: (reads clipboard, checks grammar, rewrites, copies to clipboard)
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtimes.agent.runtime import build_runtime
from runtimes.agent.tools.desktop import get_clipboard, set_clipboard
from adapters.audio.tts_router import speak

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("essay_demo")


async def grammar_check(text: str, runtime) -> str:
    """Check and fix grammar."""
    prompt = f"""Check this text for grammar and spelling errors. 
Fix any issues while preserving the meaning and style.
Return only the corrected text, no explanations.

Text:
{text}"""
    
    return await runtime.chat(prompt)


async def rewrite_with_style(text: str, style: str, runtime) -> str:
    """Rewrite text with specified style."""
    style_prompts = {
        "formal": "Rewrite this in a formal, professional tone suitable for business communication.",
        "casual": "Rewrite this in a casual, conversational tone like talking to a friend.",
        "academic": "Rewrite this in an academic tone suitable for a research paper or essay.",
        "concise": "Rewrite this to be more concise and direct, removing unnecessary words.",
        "engaging": "Rewrite this to be more engaging and compelling, suitable for a blog post.",
    }
    
    prompt = f"""{style_prompts.get(style, style_prompts["engaging"])}
Preserve the original meaning. Return only the rewritten text, no explanations.

Original:
{text}"""
    
    return await runtime.chat(prompt)


async def essay_to_editor(
    text: Optional[str] = None,
    style: str = "engaging",
    skip_grammar: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Full essay-to-editor workflow.
    
    Args:
        text: Input text (or None to read from clipboard)
        style: Target writing style
        skip_grammar: Skip grammar check (just rewrite)
        verbose: Show intermediate steps
    
    Returns:
        dict with original, grammar_fixed, rewritten, and stats
    """
    runtime = await build_runtime()
    
    # Step 1: Get text from clipboard if not provided
    if text is None:
        log.info("📋 Reading from clipboard...")
        text = await get_clipboard({}, {})
        if text.startswith("[OK]"):
            text = text.replace("[OK] clipboard: ", "").strip()
        if not text or text == "empty":
            log.error("❌ Clipboard is empty!")
            return {"error": "Empty clipboard"}
    
    original = text
    original_words = len(original.split())
    
    log.info(f"📝 Original text: {original_words} words")
    if verbose:
        log.info(f"---\n{original}\n---")
    
    # Step 2: Grammar check
    if not skip_grammar:
        log.info("🔍 Checking grammar...")
        grammar_fixed = await grammar_check(original, runtime)
        grammar_fixed = grammar_fixed.strip()
        
        if verbose:
            log.info(f"Grammar check result:\n{grammar_fixed}\n---")
    else:
        grammar_fixed = original
    
    # Step 3: Rewrite with style
    log.info(f"✨ Rewriting with {style} style...")
    rewritten = await rewrite_with_style(grammar_fixed, style, runtime)
    rewritten = rewritten.strip()
    
    rewritten_words = len(rewritten.split())
    
    if verbose:
        log.info(f"Rewritten:\n{rewritten}\n---")
    
    # Step 4: Copy to clipboard
    log.info("📋 Copying to clipboard...")
    result = await set_clipboard({"text": rewritten}, {})
    
    log.info(f"✅ Done! {original_words} → {rewritten_words} words")
    
    # Optional: Speak summary (fire-and-forget, don't await bytes)
    try:
        speak(f"Essay rewritten in {style} style. {original_words} words became {rewritten_words}.")
    except Exception:
        pass  # TTS optional
    
    return {
        "original": original,
        "grammar_fixed": grammar_fixed if not skip_grammar else None,
        "rewritten": rewritten,
        "style": style,
        "original_words": original_words,
        "rewritten_words": rewritten_words,
        "word_change": rewritten_words - original_words,
    }


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Essay to Editor Demo - Grammar check and rewrite",
    )
    parser.add_argument(
        "--style", "-s",
        choices=["formal", "casual", "academic", "concise", "engaging"],
        default="engaging",
        help="Writing style for rewrite",
    )
    parser.add_argument(
        "--text", "-t",
        help="Input text (or reads from clipboard if not provided)",
    )
    parser.add_argument(
        "--skip-grammar", "-g",
        action="store_true",
        help="Skip grammar check",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show intermediate steps",
    )
    
    args = parser.parse_args()
    
    result = asyncio.run(essay_to_editor(
        text=args.text,
        style=args.style,
        skip_grammar=args.skip_grammar,
        verbose=args.verbose,
    ))
    
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n🎉 Essay rewritten!")
    print(f"   Style: {result['style']}")
    print(f"   Words: {result['original_words']} → {result['rewritten_words']}")
    if result.get('grammar_fixed') and result['grammar_fixed'] != result['original']:
        print("   Grammar: Fixed")
    print(f"\n📋 Result copied to clipboard")


if __name__ == "__main__":
    main()
