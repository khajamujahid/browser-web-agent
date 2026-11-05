import pytest

from webhands.errors import GoalError
from webhands.goals import BOOK_GOAL, HN_GOAL
from webhands.planner import parse_goal


def test_hacker_news_goal():
    intent = parse_goal(HN_GOAL)
    assert intent.kind == "hn"
    assert intent.limit == 5
    assert intent.export == "csv"


def test_bookstore_goal():
    intent = parse_goal(BOOK_GOAL)
    assert intent.kind == "bookstore"
    assert intent.query == "Python"
    assert intent.max_price == 30
    assert intent.price_inclusive is False
    assert intent.export == "json"


def test_number_words_and_price_ceiling():
    intent = parse_goal("top five Hacker News titles")
    assert intent.limit == 5
    books = parse_goal("Search the bookstore for Python books at most $15 and save them to JSON")
    assert books.max_price == 15
    assert books.price_inclusive is True
    assert books.query == "Python"


def test_books_under_without_a_query():
    intent = parse_goal("books under $20")
    assert intent.kind == "bookstore"
    assert intent.query is None
    assert intent.max_price == 20
    assert intent.export == "json"


def test_quoted_query():
    intent = parse_goal('Search the bookstore for "data"')
    assert intent.query == "data"


def test_both_formats():
    intent = parse_goal("Hacker News titles as CSV and JSON")
    assert intent.export == "both"


def test_rejects_empty_unknown_and_mixed_goals():
    with pytest.raises(GoalError):
        parse_goal("   ")
    with pytest.raises(GoalError, match="1 and 30"):
        parse_goal("top 0 Hacker News titles")
    with pytest.raises(GoalError, match="1 and 30"):
        parse_goal("top 99 Hacker News titles")
    unknown = "weather in Lisbon"
    with pytest.raises(GoalError, match="OPENAI_API_KEY"):
        parse_goal(unknown)
    with pytest.raises(GoalError, match="Pick one"):
        parse_goal("Compare the bookstore with Hacker News")
