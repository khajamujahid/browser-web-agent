"""Turn a natural-language goal into a structured intent.

This planner is deterministic and free. It does not call a model. Unknown
goals raise GoalError so the caller can offer the optional LLM planner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from webhands.errors import GoalError
from webhands.goals import suggestion

_HN = re.compile(r"\b(hacker\s*news|y\s*combinator|hn)\b", re.I)
_STORE = re.compile(r"\b(bookstore|book\s*store|books?|catalog|catalogue)\b", re.I)
_TOP_N = re.compile(r"\b(?:top|first)\s+(\d{1,2})\b", re.I)
_TOP_WORD = re.compile(
    r"\b(?:top|first)\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b",
    re.I,
)
_PRICE_LT = re.compile(
    r"\b(?:under|below|cheaper\s+than|less\s+than)\s+\$?\s*(\d+(?:\.\d{1,2})?)",
    re.I,
)
_PRICE_LTE = re.compile(
    r"\b(?:at\s+most|no\s+more\s+than|<=)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
    re.I,
)
_QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”|\'([^\']+)\'')
_FOR_BOOKS = re.compile(r"\bfor\s+(.+?)\s+books?\b", re.I)
_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_MAX_LIMIT = 30


@dataclass(frozen=True)
class Intent:
    kind: str
    limit: int | None
    query: str | None
    max_price: float | None
    price_inclusive: bool
    export: str


def parse_goal(goal: str) -> Intent:
    text = " ".join(goal.split())
    if not text:
        raise GoalError("Give the agent a goal.\n" + suggestion())

    hn = _HN.search(text) is not None
    store = _STORE.search(text) is not None
    if hn and store:
        raise GoalError("That goal mentions both Hacker News and the bookstore. Pick one.\n" + suggestion())
    if hn:
        limit = _limit(text, default=5)
        return Intent(
            kind="hn",
            limit=limit,
            query=None,
            max_price=None,
            price_inclusive=False,
            export=_export(text, default="csv"),
        )
    if store:
        max_price, inclusive = _price(text)
        return Intent(
            kind="bookstore",
            limit=_limit(text, default=None),
            query=_query(text),
            max_price=max_price,
            price_inclusive=inclusive,
            export=_export(text, default="json"),
        )
    raise GoalError(suggestion())


def _limit(text: str, default: int | None) -> int | None:
    match = _TOP_N.search(text)
    if match:
        value = int(match.group(1))
    else:
        word = _TOP_WORD.search(text)
        if not word:
            return default
        value = _WORDS[word.group(1).lower()]
    if value < 1 or value > _MAX_LIMIT:
        raise GoalError(f"Ask for between 1 and {_MAX_LIMIT} rows.")
    return value


def _price(text: str) -> tuple[float | None, bool]:
    lesser = _PRICE_LT.search(text)
    if lesser:
        return _price_value(lesser.group(1)), False
    inclusive = _PRICE_LTE.search(text)
    if inclusive:
        return _price_value(inclusive.group(1)), True
    return None, False


def _price_value(raw: str) -> float:
    value = float(raw)
    if value < 0 or value > 100_000:
        raise GoalError("Use a price between 0 and 100000.")
    return value


def _export(text: str, default: str) -> str:
    has_csv = re.search(r"\bcsv\b", text, re.I) is not None
    has_json = re.search(r"\bjson\b", text, re.I) is not None
    if has_csv and has_json:
        return "both"
    if has_csv:
        return "csv"
    if has_json:
        return "json"
    return default


def _query(text: str) -> str | None:
    quoted = _QUOTED.search(text)
    if quoted:
        value = next(group for group in quoted.groups() if group)
        return _clean_query(value)
    match = _FOR_BOOKS.search(text)
    if match:
        return _clean_query(match.group(1))
    if re.search(r"\bpython\b", text, re.I):
        return "Python"
    return None


def _clean_query(value: str) -> str | None:
    cleaned = re.sub(r"^(the|a|an)\s+", "", value.strip(), flags=re.I)
    cleaned = cleaned.strip(" .")
    return cleaned or None
