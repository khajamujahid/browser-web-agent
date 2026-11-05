import pytest

from webhands.errors import GoalError
from webhands.llm import validate_plan
from webhands.safety import resolve_url


def test_fixture_name_resolves_inside_the_package():
    url, label = resolve_url("fixture:bookstore.html", offline=True)
    assert label == "fixture:bookstore.html"
    assert url.startswith("file:")
    assert url.endswith("bookstore.html")


def test_offline_blocks_the_public_web():
    with pytest.raises(GoalError, match="Offline mode"):
        resolve_url("https://news.ycombinator.com/", offline=True)


def test_rejects_credentials_scripts_and_private_hosts():
    with pytest.raises(GoalError):
        resolve_url("https://user:pass@news.ycombinator.com/", offline=False)
    with pytest.raises(GoalError):
        resolve_url("javascript:alert(1)", offline=False)
    with pytest.raises(GoalError):
        resolve_url("file:///etc/passwd", offline=True)
    with pytest.raises(GoalError):
        resolve_url("fixture:../secrets.html", offline=True)
    with pytest.raises(GoalError):
        resolve_url("http://127.0.0.1/", offline=False, extra_hosts={"127.0.0.1"})
    with pytest.raises(GoalError):
        resolve_url("http://localhost/", offline=False, extra_hosts={"localhost"})


def test_plan_must_extract_and_stay_short():
    with pytest.raises(GoalError, match="extract"):
        validate_plan(
            {"actions": [{"op": "goto", "url": "fixture:hackernews.html"}]},
            offline=True,
        )
    with pytest.raises(GoalError, match="Unsupported"):
        validate_plan({"actions": [{"op": "eval", "text": "alert(1)"}]}, offline=True)
    actions = validate_plan(
        {
            "actions": [
                {"op": "goto", "url": "fixture:bookstore.html"},
                {"op": "type", "selector": "#q", "text": "Python"},
                {"op": "extract", "mode": "books"},
            ]
        },
        offline=True,
    )
    assert [item.op for item in actions] == ["goto", "type", "extract"]
    assert actions[0].label == "fixture:bookstore.html"
