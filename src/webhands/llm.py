"""Optional OpenAI-compatible planner.

Disabled unless the caller passes llm=True. The default demo never imports
this module's network path.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from webhands.errors import GoalError
from webhands.safety import resolve_url

MAX_ACTIONS = 12
MAX_SELECTOR = 200
MAX_TEXT = 300
_OPS = {"goto", "click", "type", "press", "extract"}
_EXTRACT_MODES = {"hn_stories", "books", "links", "headings"}
_KEYS = {"Enter", "Tab", "Escape"}
_SELECTOR_BAD = re.compile(r"[\n\r<>]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

Transport = Callable[[str], dict]

_SYSTEM = """You plan browser actions for WebHands, a small demo agent.
Return a JSON object with one key, "actions", a list of 1 to 12 actions.
Each action has an "op" of goto, click, type, press, or extract.

goto: {"op":"goto","url":"fixture:bookstore.html"} or an https URL on an allowlisted host.
click: {"op":"click","selector":"#search"}
type: {"op":"type","selector":"#q","text":"Python"}
press: {"op":"press","selector":"#q","key":"Enter"}
extract: {"op":"extract","mode":"books"}
Extract mode is one of: hn_stories, books, links, headings.

Prefer fixture:hackernews.html and fixture:bookstore.html.
The last action must be extract.
Do not invent hosts. Do not include JavaScript, credentials, or file paths.
"""


@dataclass(frozen=True)
class Action:
    op: str
    url: str | None = None
    label: str | None = None
    selector: str | None = None
    text: str | None = None
    key: str | None = None
    mode: str | None = None


def request_plan(goal: str, *, transport: Transport | None = None) -> dict:
    if transport is not None:
        data = transport(goal)
        if not isinstance(data, dict):
            raise GoalError("LLM transport must return a JSON object.")
        return data
    return _request_openai(goal)


def validate_plan(data: dict, *, offline: bool, extra_hosts: set[str] | None = None) -> list[Action]:
    if not isinstance(data, dict):
        raise GoalError("LLM plan must be a JSON object.")
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        raise GoalError("LLM plan needs a non-empty actions list.")
    if len(actions) > MAX_ACTIONS:
        raise GoalError(f"LLM plan has more than {MAX_ACTIONS} actions.")

    planned: list[Action] = []
    for raw in actions:
        if not isinstance(raw, dict):
            raise GoalError("Each action must be an object.")
        op = raw.get("op")
        if op not in _OPS:
            raise GoalError(f"Unsupported action: {op!r}.")
        if op == "goto":
            url, label = resolve_url(str(raw.get("url", "")), offline=offline, extra_hosts=extra_hosts)
            planned.append(Action(op="goto", url=url, label=label))
        elif op == "click":
            planned.append(Action(op="click", selector=_selector(raw.get("selector"))))
        elif op == "type":
            planned.append(
                Action(op="type", selector=_selector(raw.get("selector")), text=_text(raw.get("text")))
            )
        elif op == "press":
            key = raw.get("key")
            if key not in _KEYS:
                raise GoalError("press only allows Enter, Tab, or Escape.")
            planned.append(Action(op="press", selector=_selector(raw.get("selector")), key=key))
        else:
            mode = raw.get("mode")
            if mode not in _EXTRACT_MODES:
                raise GoalError(f"Unknown extract mode: {mode!r}.")
            planned.append(Action(op="extract", mode=mode))

    if not any(item.op == "extract" for item in planned):
        raise GoalError("LLM plan must include an extract action.")
    return planned


def _selector(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoalError("Action is missing a selector.")
    selector = value.strip()
    if len(selector) > MAX_SELECTOR or _SELECTOR_BAD.search(selector):
        raise GoalError("Selector rejected.")
    return selector


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise GoalError("type needs text.")
    if len(value) > MAX_TEXT or _CONTROL.search(value):
        raise GoalError("Text rejected.")
    return value


def _request_openai(goal: str) -> dict:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise GoalError(
            "The LLM planner needs OPENAI_API_KEY. "
            "The default agent uses built-in rules and does not call an API."
        )
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": goal},
        ],
    }
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise GoalError(f"LLM planner HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GoalError(f"LLM planner could not reach the API: {exc.reason}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GoalError("LLM response did not include a message.") from exc
    return _parse_content(content)


def _parse_content(content: object) -> dict:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise GoalError("LLM message content was not JSON.")
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GoalError("LLM planner returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise GoalError("LLM planner JSON must be an object.")
    return data
