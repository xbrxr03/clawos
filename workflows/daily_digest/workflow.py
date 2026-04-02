"""daily-digest — summarize RSS/HN/local news into a daily briefing."""
from workflows.engine import WorkflowMeta, WorkflowResult, WorkflowStatus

META = WorkflowMeta(
    id          = "daily-digest",
    name        = "Daily Digest",
    category    = "content",
    description = "Summarize Hacker News top stories into a daily briefing",
    tags        = ["news", "content", "digest", "beginner"],
    requires    = [],
    destructive = False,
    timeout_s   = 90,
)


async def run(args: dict, agent) -> WorkflowResult:
    topics = args.get("topics") or "technology, AI, startups"
    count  = args.get("count") or "10"

    prompt = (
        f"Create a daily digest for topics: {topics}\n\n"
        f"1. Use web.fetch to get: https://hacker-news.firebaseio.com/v0/topstories.json\n"
        f"2. Fetch the top {count} story items from: https://hacker-news.firebaseio.com/v0/item/<id>.json\n"
        "3. Filter for stories relevant to the requested topics.\n"
        "4. Write a concise daily digest:\n\n"
        "# Daily Digest — <today's date>\n\n"
        "## Top Stories\n"
        "**1. <Title>** (<points> pts · <comments> comments)\n"
        "<one sentence summary>\n\n"
        "## Quick Takes\n"
        "<2-3 sentences on the overall theme of today's news>\n"
    )

    try:
        output = await agent.chat(prompt)
        return WorkflowResult(status=WorkflowStatus.OK, output=output)
    except Exception as exc:
        return WorkflowResult(status=WorkflowStatus.FAILED, output="", error=str(exc))
