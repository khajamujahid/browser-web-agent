import json
from pathlib import Path

from webhands.agent import Agent
from webhands.goals import BOOK_GOAL, HN_GOAL

ROOT = Path(__file__).resolve().parents[1]


def test_committed_examples_match_a_fresh_run():
    hn = Agent().run(HN_GOAL)
    books = Agent().run(BOOK_GOAL)
    outputs = ROOT / "examples" / "outputs"
    assert (outputs / "hn_top5.csv").read_text(encoding="utf-8") == hn.to_csv()
    assert json.loads((outputs / "hn_top5.json").read_text(encoding="utf-8")) == hn.to_dict()
    assert (outputs / "python_books.csv").read_text(encoding="utf-8") == books.to_csv()
    assert json.loads((outputs / "python_books.json").read_text(encoding="utf-8")) == books.to_dict()
    bundle = json.loads((ROOT / "demo" / "data" / "traces.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item["result"] for item in bundle["runs"]}
    assert by_id["hn_top5"] == hn.to_dict()
    assert by_id["python_books"] == books.to_dict()
