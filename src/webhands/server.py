"""Local FastAPI UI. One browser at a time. No LLM calls from this process."""

from __future__ import annotations

import copy
import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from webhands.agent import Agent
from webhands.errors import AgentError, GoalError
from webhands.goals import BOOK_GOAL, HN_GOAL
from webhands.paths import UI_PATH

app = FastAPI(title="WebHands", version="0.1.0")

_RUNS: dict[str, dict] = {}
_STATE = threading.Lock()
_BROWSER = threading.Lock()


class RunIn(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    live: bool = False


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return UI_PATH.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "engine": "playwright",
        "default": "offline",
        "llm": False,
    }


@app.get("/api/presets")
def presets() -> dict:
    return {
        "presets": [
            {"id": "hn", "label": "Hacker News top 5", "goal": HN_GOAL},
            {"id": "books", "label": "Python books under $30", "goal": BOOK_GOAL},
        ]
    }


@app.post("/api/runs", status_code=202)
def start_run(body: RunIn) -> dict:
    goal = " ".join(body.goal.split())
    if not goal:
        raise HTTPException(status_code=400, detail="Give the agent a goal.")
    if not _BROWSER.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="An agent is already browsing. Wait for it to finish.",
        )
    run_id = uuid.uuid4().hex[:12]
    with _STATE:
        _RUNS[run_id] = {
            "id": run_id,
            "goal": goal,
            "live": body.live,
            "status": "running",
            "steps": [],
            "rows": [],
            "columns": [],
            "error": None,
            "mode": None,
            "planner": None,
            "export": None,
            "csv": "",
            "json": "",
        }
        _prune_locked()

    def on_step(step) -> None:
        with _STATE:
            _RUNS[run_id]["steps"].append(step.to_dict())

    def worker() -> None:
        try:
            agent = Agent(offline=not body.live, headless=True, llm=False, on_step=on_step)
            result = agent.run(goal)
            with _STATE:
                _RUNS[run_id].update(
                    status="done",
                    rows=result.rows,
                    columns=result.columns,
                    mode=result.mode,
                    planner=result.planner,
                    export=result.export,
                    csv=result.to_csv(),
                    json=result.to_json(),
                )
        except (GoalError, AgentError) as exc:
            with _STATE:
                _RUNS[run_id]["status"] = "error"
                _RUNS[run_id]["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001 — surface a short message in the UI
            with _STATE:
                _RUNS[run_id]["status"] = "error"
                _RUNS[run_id]["error"] = str(exc).splitlines()[0][:300]
        finally:
            _BROWSER.release()

    try:
        threading.Thread(target=worker, name=f"webhands-{run_id}", daemon=True).start()
    except Exception:
        _BROWSER.release()
        raise
    return {"id": run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    with _STATE:
        run = _RUNS.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Unknown run.")
        return copy.deepcopy(run)


def _prune_locked() -> None:
    finished = [key for key, value in _RUNS.items() if value["status"] != "running"]
    overflow = len(_RUNS) - 30
    for key in finished[: max(0, overflow)]:
        _RUNS.pop(key, None)
