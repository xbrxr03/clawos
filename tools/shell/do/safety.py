# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS /do — Safety classifier
================================
3-tier danger detection via regex pattern matching. No LLM call required.
Tier 1 — safe:     show [y/n], default YES
Tier 2 — dangerous: show [y/N], default NO
Tier 3 — critical:  must type 'yes' in full

--yes flag NEVER bypasses dangerous or critical. Ever.
"""
import re
from dataclasses import dataclass
from typing import Literal

Tier = Literal["safe", "dangerous", "critical"]

# ── Danger patterns ────────────────────────────────────────────────────────────
_CRITICAL_PATTERNS = [
    r"rm\s+-[a-z]*r[a-z]*f?\s+/(\s|$)",     # rm -rf / (slash at end or before more args)
    r"rm\s+-[a-z]*f[a-z]*r?\s+/(\s|$)",     # rm -fr /
    r"dd\s+.*of=/dev/(s|h|v|xv)d[a-z]\b",  # dd to whole disk
    r"dd\s+.*of=/dev/nvme\d+n\d+\b",        # dd to nvme whole disk
    r"mkfs\s+/dev/(s|h)d[a-z]\b",           # mkfs on whole disk (no partition number)
    r"shred\s+.*-[a-z]*n\s*[3-9]",          # shred with many passes
    r":(){ :|:& };:",                        # fork bomb
    r"\bpoweroff\b|\breboot\b|\bshutdown\b", # system shutdown
]

_DANGEROUS_PATTERNS = [
    r"\brm\s+-[a-z]*r",                     # rm -r (recursive)
    r"\brm\s+-[a-z]*f",                     # rm -f (force)
    r"\bdd\b.*\bof=",                        # dd writing anywhere
    r"\bmkfs\b",                             # any mkfs
    r"\bchmod\s+[0-7]*7[0-7][0-7]\b",       # chmod 7xx (world-writable)
    r"\bchmod\s+a\+w\b",                     # chmod a+w
    r"\bchown\s+-R\b",                       # recursive chown
    r"\bkill\s+-9\b",                        # SIGKILL
    r"\bkillall\b",                          # killall
    r"\bpkill\b",                            # pkill
    r"\bcrontab\s+-r\b",                     # delete all crons
    r"\biptables\s+-F\b",                    # flush firewall
    r"\biptables\s+-X\b",                    # delete chains
    r"\bsudo\s+su\b",                        # sudo su
    r"\bsu\s+-\b",                           # su - root
    r"\bpasswd\b",                           # change passwords
    r"\btruncate\b",                         # truncate files
    r"\bshred\b",                            # shred (any)
    r"\bwipe\b",                             # wipe
    r"\bsystemctl\s+(disable|mask|stop)\b",  # systemctl dangerous ops
    r">\s*/etc/",                            # overwrite /etc/ files
    r"\bsed\s+-i\b.*\b/etc/",               # in-place edit /etc/
    r"\bsudo\s+rm\b",                        # sudo rm
    r"\bsudo\s+dd\b",                        # sudo dd
    r"\bnohup\b.*&",                         # background nohup (potentially persistent)
    r"2>/dev/null\s*&\s*$",                  # silent backgrounding
    r"\beval\b",                             # eval (code injection risk)
    r"\bcurl\b.*\|\s*(ba)?sh\b",             # curl | sh
    r"\bwget\b.*-O-.*\|\s*(ba)?sh\b",        # wget | sh
    r"\bpip\b.*--system\b",                  # pip --system installs
]

# Safe patterns that override dangerous matches (false positive prevention)
_SAFE_OVERRIDES = [
    r"\brm\s+\S+\.(log|tmp|cache|pyc|o|class)\b",   # rm specific safe files
    r"\bchmod\s+[0-7]*(644|755|600|400)\b",          # common safe permissions
    r"\bchmod\s+[ugo][+-][rwx]\b",                   # targeted permission changes
    r"\bkill\s+-9\s+\$\$\b",                         # kill current process only
]


@dataclass
class SafetyResult:
    tier: Tier
    matched_pattern: str = ""
    warning: str = ""


def classify(command: str) -> SafetyResult:
    """Classify a single shell command string."""
    cmd = command.strip()
    if not cmd:
        return SafetyResult(tier="safe")

    # Check critical first
    for pat in _CRITICAL_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return SafetyResult(
                tier="critical",
                matched_pattern=pat,
                warning="This command could cause irreversible system damage.",
            )

    # Check dangerous
    for pat in _DANGEROUS_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            # Check safe overrides
            overridden = any(
                re.search(override, cmd, re.IGNORECASE)
                for override in _SAFE_OVERRIDES
            )
            if not overridden:
                return SafetyResult(
                    tier="dangerous",
                    matched_pattern=pat,
                    warning="This command may cause data loss or system changes.",
                )

    return SafetyResult(tier="safe")


def classify_plan(commands: list[str]) -> SafetyResult:
    """
    Classify a multi-step plan. Returns the worst tier found across all commands.
    If any command is critical, the whole plan is critical.
    """
    worst = SafetyResult(tier="safe")
    order = {"safe": 0, "dangerous": 1, "critical": 2}
    for cmd in commands:
        result = classify(cmd)
        if order[result.tier] > order[worst.tier]:
            worst = result
    return worst


def is_safe(command: str) -> bool:
    return classify(command).tier == "safe"


def is_dangerous(command: str) -> bool:
    return classify(command).tier in ("dangerous", "critical")


def is_critical(command: str) -> bool:
    return classify(command).tier == "critical"
