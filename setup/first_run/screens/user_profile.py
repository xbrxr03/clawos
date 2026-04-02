"""Screen — user_profile: ask what the user mainly uses this machine for."""

_PROFILES = [
    ("developer",        "Developer",        "coding, git, repos, code review"),
    ("content_creator",  "Content Creator",  "writing, images, captions, digests"),
    ("researcher",       "Researcher",       "PDFs, notes, summarization"),
    ("business",         "Business",         "spreadsheets, reports, CSV data"),
    ("general",          "General",          "a bit of everything"),
]


def run(state) -> bool:
    print("\n  ── What do you mainly use this machine for? ────")
    print()
    for i, (key, label, desc) in enumerate(_PROFILES, 1):
        print(f"  [{i}] {label:<18}  {desc}")
    print()
    try:
        choice = input("  Choose [1-5] or Enter to skip: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    if choice.isdigit() and 1 <= int(choice) <= len(_PROFILES):
        state.user_profile = _PROFILES[int(choice) - 1][0]
        label = _PROFILES[int(choice) - 1][1]
        print(f"\n  Profile set: {label}")
        print("  ClawOS will suggest workflows tailored to you.")
    else:
        state.user_profile = "general"
        print("\n  Profile: General")

    state.mark_done("user_profile")
    return True
