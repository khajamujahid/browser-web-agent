"""Command line for one-shot runs and the local UI."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from webhands import __version__
from webhands.errors import AgentError, GoalError
from webhands.goals import BOOK_GOAL, HN_GOAL


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] not in {"run", "serve", "-h", "--help", "--version"} and not args[0].startswith("-"):
        args = ["run", *args]
    parser = argparse.ArgumentParser(
        prog="webhands",
        description="WebHands drives a real browser from a natural-language goal.",
    )
    parser.add_argument("--version", action="version", version=f"webhands {__version__}")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Plan a goal and write CSV or JSON")
    run.add_argument("goal", help="What the agent should do")
    run.add_argument("-o", "--output", help="File to write. Suffix picks csv or json when --format is auto.")
    run.add_argument("--format", choices=("auto", "csv", "json", "both"), default="auto")
    run.add_argument("--live", action="store_true", help="Read the public Hacker News front page")
    run.add_argument("--llm", action="store_true", help="Use the optional LLM planner (needs OPENAI_API_KEY)")
    run.add_argument("--headed", action="store_true", help="Show the Chromium window")
    run.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="Extra public host the LLM planner may open (repeatable)",
    )

    serve = sub.add_parser("serve", help="Start the local UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    parsed = parser.parse_args(args)
    if parsed.command == "serve":
        return _serve(parsed.host, parsed.port)
    if parsed.command != "run":
        parser.print_help()
        return 2
    try:
        return _run(parsed)
    except GoalError as exc:
        print(f"webhands: {exc}", file=sys.stderr)
        return 2
    except AgentError as exc:
        print(f"webhands: {exc}", file=sys.stderr)
        return 1


def _run(parsed: argparse.Namespace) -> int:
    from webhands.agent import Agent

    llm = parsed.llm or _flag(os.environ.get("WEBHANDS_LLM", ""))
    headed = parsed.headed or _flag(os.environ.get("WEBHANDS_HEADED", ""))
    agent = Agent(
        offline=not parsed.live,
        headless=not headed,
        llm=llm,
        extra_hosts=set(parsed.allow_host),
    )
    result = agent.run(parsed.goal)
    _print_result(result)
    if parsed.output:
        paths = _write(result, Path(parsed.output), parsed.format)
        for path in paths:
            print(f"wrote     {path}")
    else:
        print("\nPass -o to write a file. Example goals:")
        print(f"  webhands run {HN_GOAL!r} -o hn.csv")
        print(f"  webhands run {BOOK_GOAL!r} -o books.json")
    return 0


def _write(result, path: Path, fmt: str) -> list[Path]:
    chosen = fmt
    if chosen == "auto":
        if path.suffix.lower() == ".csv":
            chosen = "csv"
        elif path.suffix.lower() == ".json":
            chosen = "json"
        else:
            chosen = result.export if result.export in {"csv", "json", "both"} else "csv"
    written: list[Path] = []
    if chosen in {"csv", "both"}:
        target = path if path.suffix.lower() == ".csv" and chosen == "csv" else path.with_suffix(".csv")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.to_csv(), encoding="utf-8")
        written.append(target)
    if chosen in {"json", "both"}:
        target = path if path.suffix.lower() == ".json" and chosen == "json" else path.with_suffix(".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.to_json(), encoding="utf-8")
        written.append(target)
    return written


def _print_result(result) -> None:
    print(f"webhands  {result.mode} · {result.planner}")
    print(f"goal      {result.goal}")
    print()
    for step in result.steps:
        mark = "ok  " if step.ok else "fail"
        print(f"  {step.n:>2}  {mark} {step.op:<8} {step.detail}")
        if step.observation:
            print(f"           {step.observation}")
    print()
    print(_table(result.columns, result.rows))
    print()
    print(result.summary())


def _table(columns: list[str], rows: list[dict]) -> str:
    if not columns:
        return "(no columns)"
    shown = rows[:20]
    headers = [column.upper() for column in columns]
    rendered = [[_clip(row.get(column, "")) for column in columns] for row in shown]
    widths = []
    for index, header in enumerate(headers):
        cell_width = max((len(item[index]) for item in rendered), default=0)
        widths.append(max(len(header), cell_width))
    rule = "  ".join("-" * width for width in widths)
    lines = ["  ".join(header.ljust(width) for header, width in zip(headers, widths)), rule]
    for item in rendered:
        lines.append("  ".join(value.ljust(width) for value, width in zip(item, widths)))
    if len(rows) > len(shown):
        lines.append(f"... {len(rows) - len(shown)} more rows")
    if not shown:
        lines.append("(no rows)")
    return "\n".join(lines)


def _clip(value: object, limit: int = 72) -> str:
    text = str(value).replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _serve(host: str, port: int) -> int:
    import uvicorn

    from webhands.server import app

    print(f"WebHands UI  http://{host}:{port}")
    print("Offline fixtures only, unless you check Live Hacker News.")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
