"""Write example artifacts and the static demo bundle."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "examples" / "outputs"
DEMO_TRACES = ROOT / "demo" / "data" / "traces.json"
LABELS = {
    "hn_top5": "Hacker News top 5",
    "python_books": "Python books under $30",
}
ORDER = {"hn_top5": 0, "python_books": 1}


def write_run(result, stem: str) -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / f"{stem}.csv").write_text(result.to_csv(), encoding="utf-8")
    (OUTPUTS / f"{stem}.json").write_text(result.to_json(), encoding="utf-8")

    DEMO_TRACES.parent.mkdir(parents=True, exist_ok=True)
    bundle = {"runs": []}
    if DEMO_TRACES.is_file():
        bundle = json.loads(DEMO_TRACES.read_text(encoding="utf-8"))
    runs = [item for item in bundle.get("runs", []) if item.get("id") != stem]
    runs.append(
        {
            "id": stem,
            "label": LABELS.get(stem, stem),
            "result": result.to_dict(),
        }
    )
    runs.sort(key=lambda item: ORDER.get(item["id"], 9))
    DEMO_TRACES.write_text(
        json.dumps({"runs": runs}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUTS / (stem + '.csv')}")
    print(f"wrote {OUTPUTS / (stem + '.json')}")
