"""ClawOS terminal UI — banner, tables, status icons."""
from clawos_core.constants import VERSION_FULL

BANNER = f"""
  ██████╗██╗      █████╗ ██╗    ██╗ ██████╗ ███████╗
 ██╔════╝██║     ██╔══██╗██║    ██║██╔═══██╗██╔════╝
 ██║     ██║     ███████║██║ █╗ ██║██║   ██║███████╗
 ██║     ██║     ██╔══██║██║███╗██║██║   ██║╚════██║
 ╚██████╗███████╗██║  ██║╚███╔███╔╝╚██████╔╝███████║
  ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝
  {VERSION_FULL} | local · offline · private
"""

MINI = "  [ClawOS] "


def print_banner():
    print(BANNER)


def status_icon(status: str) -> str:
    return {
        "active":    "✓",
        "running":   "✓",
        "inactive":  "○",
        "failed":    "✗",
        "unknown":   "?",
        "ok":        "✓",
        "down":      "✗",
    }.get(status.lower(), "?")


def table(rows: list[tuple], headers: tuple = None):
    if not rows:
        print("  (empty)")
        return
    all_rows = ([headers] + list(rows)) if headers else list(rows)
    widths = [max(len(str(r[i])) for r in all_rows) for i in range(len(all_rows[0]))]
    if headers:
        h = "  " + "  ".join(str(headers[i]).ljust(widths[i]) for i in range(len(headers)))
        print(h)
        print("  " + "  ".join("─" * widths[i] for i in range(len(widths))))
        rows = list(rows)
    for row in rows:
        print("  " + "  ".join(str(row[i]).ljust(widths[i]) for i in range(len(row))))


def success(msg: str): print(f"  ✓  {msg}")
def error(msg: str):   print(f"  ✗  {msg}")
def info(msg: str):    print(f"  ·  {msg}")
def warn(msg: str):    print(f"  ⚠  {msg}")
