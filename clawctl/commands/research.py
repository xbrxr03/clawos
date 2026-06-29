# SPDX-License-Identifier: AGPL-3.0-or-later
"""clawctl research — deep research with citations."""
from services.researchd.engine import get_engine, ResearchSession


def run_start(query: str, urls: str = ""):
    """Start a research session."""
    seed_urls = [u.strip() for u in urls.split(",") if u.strip()] if urls else None
    engine = get_engine()
    from clawctl.ui.banner import info, success

    print()
    info(f"Researching: {query}")
    if seed_urls:
        info(f"Seed URLs: {', '.join(seed_urls)}")

    session = engine.start_session(query=query, seed_urls=seed_urls)

    # Fetch sources
    info("Fetching sources...")
    session = engine.fetch_sources(session)

    # Display results
    fetched = [s for s in session.sources if s.fetched]
    errors = [s for s in session.sources if s.error]

    success(f"Found {len(session.sources)} sources ({len(fetched)} fetched, {len(errors)} errors)")
    print(f"  Session ID: {session.id}")
    print(f"  Provider: {session.provider}")
    print()

    if session.citations:
        print("  CITATIONS:")
        for i, c in enumerate(session.citations[:8], 1):
            emoji = "🟢" if c.relevance == "primary" else "🔵" if c.relevance == "supporting" else "⚪"
            print(f"  {emoji} {i}. {c.title}")
            print(f"     {c.url}")
            print(f"     \"{c.excerpt[:120]}...\"")
            print()

    if not session.citations and fetched:
        print("  SOURCES (no citations extracted — try a more specific query):")
        for s in fetched[:5]:
            print(f"  · {s.title}")
            print(f"    {s.url}")
        print()

    print(f"  Resume with: clawctl research get {session.id}")
    print(f"  Re-fetch:    clawctl research fetch {session.id}")
    print()


def run_list():
    """List all research sessions."""
    from clawctl.ui.banner import info

    sessions = ResearchSession.list_all()
    print()
    if not sessions:
        info("No research sessions found")
        print("  Start one: clawctl research start 'your query'")
        print()
        return

    info(f"Research sessions ({len(sessions)})")
    print()
    fmt = "  {:<12} {:<8} {:<8} {:<6}  {}"
    print(fmt.format("ID", "STATUS", "PROVIDER", "SRCS", "QUERY"))
    print("  " + "─" * 70)
    for s in sessions:
        print(fmt.format(
            s["id"][:10],
            s["status"],
            s["provider"],
            str(s["source_count"]),
            s["query"][:40],
        ))
    print()


def run_get(session_id: str):
    """Show a research session."""
    from clawctl.ui.banner import info, error

    session = ResearchSession.load(session_id)
    if not session:
        error(f"Session not found: {session_id}")
        print()
        return

    print()
    info(f"Research: {session.query}")
    print(f"  ID:       {session.id}")
    print(f"  Status:   {session.status}")
    print(f"  Provider: {session.provider}")
    print(f"  Sources:  {len(session.sources)}")
    print(f"  Citations: {len(session.citations)}")
    if session.summary:
        print(f"  Summary:  {session.summary[:200]}")
    print()

    if session.citations:
        print("  CITATIONS:")
        for i, c in enumerate(session.citations, 1):
            emoji = "🟢" if c.relevance == "primary" else "🔵" if c.relevance == "supporting" else "⚪"
            print(f"  {emoji} {i}. [{c.relevance}] {c.title}")
            print(f"     {c.url}")
            print(f"     \"{c.excerpt[:150]}\"")
        print()

    [s for s in session.sources if s.fetched]
    unfetched = [s for s in session.sources if not s.fetched and not s.error]
    errored = [s for s in session.sources if s.error]

    if unfetched:
        print(f"  Unfetched sources ({len(unfetched)}):")
        for s in unfetched:
            print(f"    · {s.url}")
        print(f"  Run: clawctl research fetch {session.id}")
        print()

    if errored:
        print(f"  Failed sources ({len(errored)}):")
        for s in errored[:3]:
            print(f"    · {s.url}: {s.error[:60]}")
        print()


def run_fetch(session_id: str):
    """Re-fetch sources for a session."""
    from clawctl.ui.banner import info, success, error

    session = ResearchSession.load(session_id)
    if not session:
        error(f"Session not found: {session_id}")
        print()
        return

    engine = get_engine()
    info("Fetching sources...")
    session = engine.fetch_sources(session)
    fetched = [s for s in session.sources if s.fetched]
    success(f"Fetched {len(fetched)}/{len(session.sources)} sources")
    if session.citations:
        print(f"  Citations: {len(session.citations)}")
    print()


def run_delete(session_id: str):
    """Delete a research session."""
    from clawctl.ui.banner import success, error

    engine = get_engine()
    ok = engine.delete_session(session_id)
    if ok:
        success(f"Deleted session {session_id}")
    else:
        error(f"Session not found: {session_id}")
    print()