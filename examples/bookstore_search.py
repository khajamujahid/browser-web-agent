#!/usr/bin/env python3
"""Search the local bookstore for Python books under $30 and save JSON.

    python examples/bookstore_search.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from _shared import write_run
from webhands import Agent
from webhands.goals import BOOK_GOAL


def main() -> int:
    result = Agent(offline=True, headless=True).run(BOOK_GOAL)
    write_run(result, "python_books")
    print(result.summary())
    for row in result.rows:
        print(f"  {row['title']}  ${row['price']}  {row['author']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
