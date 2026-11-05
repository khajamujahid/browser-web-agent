import json

import pytest

from webhands.agent import Agent
from webhands.errors import GoalError
from webhands.exporters import rows_to_csv
from webhands.goals import BOOK_GOAL, HN_GOAL
from webhands.llm import request_plan


def test_csv_quotes_commas():
    text = rows_to_csv(["title"], [{"title": "CSS selectors, explained"}])
    assert text == 'title\n"CSS selectors, explained"\n'


def test_hacker_news_offline_top_five():
    result = Agent().run(HN_GOAL)
    assert result.mode == "offline"
    assert result.planner == "rules"
    assert [step.op for step in result.steps] == ["parse", "goto", "extract", "limit"]
    assert result.steps[1].detail == "fixture:hackernews.html"
    assert "Hacker News" in result.steps[1].observation
    assert [row["title"] for row in result.rows] == [
        "Show HN: A browser agent that writes CSV, then stops",
        "Playwright traces got small enough to read",
        "Local-first agents for people who do not want a cloud browser",
        "CSS selectors, explained without the magic",
        "Ask HN: How do you test scrapers with the network unplugged?",
    ]
    assert result.rows[0]["points"] == 142
    assert result.rows[0]["comments"] == 38
    assert "/home/" not in result.to_json()
    assert "file:" not in result.to_json()


def test_hacker_news_keeps_only_what_the_page_has():
    result = Agent().run("Get the top 20 Hacker News titles")
    assert len(result.rows) == 12
    assert "only had 12" in result.steps[-1].observation


def test_bookstore_search_types_clicks_and_filters():
    result = Agent().run(BOOK_GOAL)
    titles = [row["title"] for row in result.rows]
    assert titles == [
        "Think Python",
        "Automate the Boring Stuff with Python",
        "Python Crash Course",
        "Web Scraping with Python",
    ]
    assert "Fluent Python" not in titles
    assert [step.op for step in result.steps] == [
        "parse",
        "goto",
        "type",
        "click",
        "type",
        "click",
        "extract",
    ]
    assert result.rows[0]["price"] == "15.00"
    assert result.export == "json"


def test_at_most_includes_the_boundary_price():
    result = Agent().run("Search the bookstore for Python books at most $15 and save them to JSON")
    assert [row["title"] for row in result.rows] == [
        "Think Python",
        "Automate the Boring Stuff with Python",
    ]


def test_live_bookstore_is_refused_before_a_browser_session():
    with pytest.raises(GoalError, match="local fixture"):
        Agent(offline=False).run(BOOK_GOAL)


def test_llm_loop_can_drive_the_bookstore():
    def transport(goal: str) -> dict:
        assert "Python" in goal
        return {
            "actions": [
                {"op": "goto", "url": "fixture:bookstore.html"},
                {"op": "type", "selector": "#q", "text": "Python"},
                {"op": "click", "selector": "#mode-lt"},
                {"op": "type", "selector": "#max", "text": "30"},
                {"op": "click", "selector": "#search"},
                {"op": "extract", "mode": "books"},
            ]
        }

    result = Agent(llm=True, llm_transport=transport).run("Find Python books")
    assert result.planner == "llm"
    assert len(result.rows) == 4
    assert result.steps[0].op == "plan"


def test_llm_rejects_a_hostile_plan_without_browsing():
    def transport(goal: str) -> dict:
        return {"actions": [{"op": "goto", "url": "javascript:alert(1)"}, {"op": "extract", "mode": "links"}]}

    with pytest.raises(GoalError):
        Agent(llm=True, llm_transport=transport).run("ignore the rules")


def test_llm_requires_a_key_when_there_is_no_transport(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(GoalError, match="OPENAI_API_KEY"):
        request_plan("open the bookstore")


def test_json_dump_is_stable():
    result = Agent().run(HN_GOAL)
    again = json.loads(result.to_json())
    assert again == result.to_dict()
