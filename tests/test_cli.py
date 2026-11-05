from webhands.cli import main
from webhands.goals import BOOK_GOAL, HN_GOAL


def test_cli_writes_csv(tmp_path):
    path = tmp_path / "hn.csv"
    code = main(["run", HN_GOAL, "-o", str(path)])
    assert code == 0
    text = path.read_text(encoding="utf-8")
    assert text.startswith("rank,title,url,points,comments\n")
    assert "Show HN: A browser agent that writes CSV, then stops" in text


def test_cli_writes_json_from_a_bare_goal(tmp_path):
    path = tmp_path / "books.json"
    code = main([BOOK_GOAL, "-o", str(path)])
    assert code == 0
    assert '"Think Python"' in path.read_text(encoding="utf-8")


def test_cli_unknown_goal_is_a_usage_error():
    assert main(["run", "weather in Lisbon"]) == 2
