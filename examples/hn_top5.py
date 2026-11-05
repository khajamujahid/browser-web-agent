#!/usr/bin/env python3
"""Save the top 5 Hacker News titles to CSV.

Offline by default: this reads the local fixture, not the public internet.

    python examples/hn_top5.py
    python examples/hn_top5.py --live
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from _shared import write_run
from webhands import Agent
from webhands.goals import HN_GOAL


def main() -> int:
    live = "--live" in sys.argv[1:]
    result = Agent(offline=not live, headless=True).run(HN_GOAL)
    write_run(result, "hn_top5")
    print(result.summary())
    for row in result.rows:
        print(f"  {row['rank']:>2}. {row['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
