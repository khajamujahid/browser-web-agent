"""Agent loop: plan a goal, drive Playwright, return rows and a step trace."""

from __future__ import annotations

from collections.abc import Callable

from webhands.errors import AgentError, GoalError
from webhands.executor import BrowserSession, explain_browser_error
from webhands.goals import BOOK_FIXTURE, HN_FIXTURE, HN_LIVE_URL
from webhands.llm import request_plan, validate_plan
from webhands.models import RunResult, Step
from webhands.planner import Intent, parse_goal
from webhands.safety import display_target, fixture_page

StepCallback = Callable[[Step], None]


class Agent:
    """Run one natural-language goal.

    offline=True (the default) only opens the packaged HTML fixtures.
    llm=True opts into the OpenAI-compatible planner. Without it, planning is
    a local rules pass and no network call is made.
    """

    def __init__(
        self,
        *,
        offline: bool = True,
        headless: bool = True,
        llm: bool = False,
        on_step: StepCallback | None = None,
        llm_transport=None,
        extra_hosts: set[str] | None = None,
    ) -> None:
        self.offline = offline
        self.headless = headless
        self.llm = llm
        self.on_step = on_step
        self.llm_transport = llm_transport
        self.extra_hosts = extra_hosts or set()

    def run(self, goal: str) -> RunResult:
        text = " ".join(goal.split())
        if not text:
            raise GoalError("Give the agent a goal.")
        if self.llm:
            return self._run_llm(text)
        intent = parse_goal(text)
        steps: list[Step] = []
        self._emit(steps, "parse", _parse_detail(intent), _parse_observation(intent))
        if intent.kind == "bookstore" and not self.offline:
            raise GoalError("The bookstore is a local fixture. Run it without --live.")
        try:
            with BrowserSession(headless=self.headless) as session:
                if intent.kind == "hn":
                    columns, rows = self._hn(session, intent, steps)
                elif intent.kind == "bookstore":
                    columns, rows = self._books(session, intent, steps)
                else:
                    raise GoalError(f"Unknown task: {intent.kind}")
        except (GoalError, AgentError):
            raise
        except Exception as exc:
            raise AgentError(explain_browser_error(exc), steps) from exc
        return RunResult(
            goal=text,
            mode="offline" if self.offline else "live",
            planner="rules",
            export=intent.export,
            steps=steps,
            columns=columns,
            rows=rows,
        )

    def _run_llm(self, goal: str) -> RunResult:
        steps: list[Step] = []
        plan = request_plan(goal, transport=self.llm_transport)
        actions = validate_plan(plan, offline=self.offline, extra_hosts=self.extra_hosts)
        self._emit(
            steps,
            "plan",
            "LLM planner",
            f"{len(actions)} actions. URLs stay on fixtures or the allowlist.",
        )
        columns: list[str] = []
        rows: list[dict] = []
        try:
            with BrowserSession(headless=self.headless) as session:
                for action in actions:
                    if action.op == "goto":
                        title = session.goto(action.url or "")
                        self._emit(steps, "goto", action.label or display_target(action.url or ""), f"Page title: {title}")
                    elif action.op == "click":
                        session.click(action.selector or "")
                        self._emit(steps, "click", action.selector or "", "Clicked.")
                    elif action.op == "type":
                        session.fill(action.selector or "", action.text or "")
                        self._emit(steps, "type", action.selector or "", f'Typed "{action.text}".')
                    elif action.op == "press":
                        session.press(action.selector or "", action.key or "")
                        self._emit(steps, "press", action.selector or "", f"Pressed {action.key}.")
                    elif action.op == "extract":
                        columns, rows = session.extract(action.mode or "")
                        self._emit(steps, "extract", action.mode or "", f"Read {len(rows)} rows.")
        except (GoalError, AgentError):
            raise
        except Exception as exc:
            raise AgentError(explain_browser_error(exc), steps) from exc
        return RunResult(
            goal=goal,
            mode="offline" if self.offline else "live",
            planner="llm",
            export="json",
            steps=steps,
            columns=columns,
            rows=rows,
        )

    def _hn(self, session: BrowserSession, intent: Intent, steps: list[Step]) -> tuple[list[str], list[dict]]:
        if self.offline:
            url = fixture_page(HN_FIXTURE)
            label = f"fixture:{HN_FIXTURE}"
        else:
            url = HN_LIVE_URL
            label = HN_LIVE_URL
        title = session.goto(url)
        self._emit(steps, "goto", label, f"Page title: {title}")
        session.wait("tr.athing")
        columns, rows = session.extract("hn_stories")
        self._emit(steps, "extract", "Front-page stories", f"Found {len(rows)} stories.")
        if not rows:
            raise AgentError(
                "No stories found. The offline fixture is the supported demo; "
                "the live front page may have changed.",
                steps,
            )
        limit = intent.limit or len(rows)
        kept = rows[:limit]
        if len(rows) < limit:
            note = f"Kept {len(kept)}. The page only had {len(rows)}."
        else:
            note = f"Kept {len(kept)}."
        self._emit(steps, "limit", f"Keep {limit}", note)
        return columns, kept

    def _books(self, session: BrowserSession, intent: Intent, steps: list[Step]) -> tuple[list[str], list[dict]]:
        url = fixture_page(BOOK_FIXTURE)
        title = session.goto(url)
        self._emit(steps, "goto", f"fixture:{BOOK_FIXTURE}", f"Page title: {title}")
        if intent.query:
            session.fill("#q", intent.query)
            self._emit(steps, "type", "#q", f'Typed "{intent.query}" into the search box.')
        if intent.max_price is not None:
            mode_selector = "#mode-lte" if intent.price_inclusive else "#mode-lt"
            mode_label = "at most" if intent.price_inclusive else "under"
            session.click(mode_selector)
            self._emit(steps, "click", mode_selector, f"Set the price comparison to {mode_label}.")
            typed = _format_price(intent.max_price)
            session.fill("#max", typed)
            self._emit(steps, "type", "#max", f'Typed "{typed}" into the max price.')
        session.click("#search")
        session.page.wait_for_function(
            "() => (document.querySelector('#status')?.textContent || '').includes('book')"
        )
        self._emit(steps, "click", "#search", "Submitted the search form.")
        columns, rows = session.extract("books")
        self._emit(steps, "extract", "Matching books", f"Found {len(rows)} books.")
        if intent.limit is not None:
            rows = rows[: intent.limit]
            self._emit(steps, "limit", f"Keep {intent.limit}", f"Kept {len(rows)}.")
        return columns, rows

    def _emit(
        self,
        steps: list[Step],
        op: str,
        detail: str,
        observation: str = "",
        *,
        ok: bool = True,
    ) -> Step:
        step = Step(n=len(steps) + 1, op=op, detail=detail, observation=observation, ok=ok)
        steps.append(step)
        if self.on_step is not None:
            self.on_step(step)
        return step


def _parse_detail(intent: Intent) -> str:
    if intent.kind == "hn":
        return "Hacker News front page"
    return "Bookstore search"


def _parse_observation(intent: Intent) -> str:
    export = {"csv": "CSV", "json": "JSON", "both": "CSV and JSON"}[intent.export]
    if intent.kind == "hn":
        return f"Top {intent.limit} stories. Export {export}. Rules planner, no API call."
    query = f'Query "{intent.query}". ' if intent.query else "No search text. "
    if intent.max_price is None:
        price = "No price ceiling. "
    else:
        word = "at most" if intent.price_inclusive else "under"
        price = f"Price {word} {_format_price(intent.max_price)}. "
    return f"{query}{price}Export {export}. Rules planner, no API call."


def _format_price(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"
