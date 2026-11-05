import time

from fastapi.testclient import TestClient

from webhands.goals import BOOK_GOAL, HN_GOAL
from webhands.server import app


def _wait(client: TestClient, run_id: str) -> dict:
    deadline = time.time() + 40
    body = {}
    while time.time() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.1)
    raise AssertionError(body)


def test_health_presets_and_page():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["engine"] == "playwright"
        assert health.json()["llm"] is False
        goals = [item["goal"] for item in client.get("/api/presets").json()["presets"]]
        assert goals == [HN_GOAL, BOOK_GOAL]
        page = client.get("/")
        assert page.status_code == 200
        assert HN_GOAL in page.text
        assert "cannot launch Playwright" in page.text


def test_api_run_returns_rows_and_csv():
    with TestClient(app) as client:
        created = client.post("/api/runs", json={"goal": HN_GOAL})
        assert created.status_code == 202
        body = _wait(client, created.json()["id"])
        assert body["status"] == "done"
        assert len(body["rows"]) == 5
        assert body["csv"].splitlines()[0] == "rank,title,url,points,comments"
        assert body["planner"] == "rules"


def test_api_refuses_a_live_bookstore():
    with TestClient(app) as client:
        created = client.post("/api/runs", json={"goal": BOOK_GOAL, "live": True})
        body = _wait(client, created.json()["id"])
        assert body["status"] == "error"
        assert "local fixture" in body["error"]
