"""Canonical goals shared by the CLI, UI, examples, and tests."""

HN_GOAL = "Get the top 5 Hacker News titles and save them to CSV"
BOOK_GOAL = "Search the bookstore for Python books under $30 and save them to JSON"

HN_FIXTURE = "hackernews.html"
BOOK_FIXTURE = "bookstore.html"
HN_LIVE_URL = "https://news.ycombinator.com/"


def suggestion() -> str:
    return (
        "This demo understands two offline goals:\n"
        f"  - {HN_GOAL}\n"
        f"  - {BOOK_GOAL}\n"
        "For any other goal, opt in to the LLM planner: "
        'webhands run --llm "..." (needs OPENAI_API_KEY). '
        "The default path stays free and does not call an API."
    )
