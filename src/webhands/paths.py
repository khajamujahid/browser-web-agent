"""Package paths for fixtures and the UI."""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = PACKAGE_DIR / "fixtures"
UI_PATH = PACKAGE_DIR / "ui" / "index.html"


def fixture_path(name: str) -> Path:
    """Return a fixture HTML file. Rejects path traversal."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError(f"Unknown fixture: {name}")
    path = (FIXTURES_DIR / name).resolve()
    if path.parent != FIXTURES_DIR.resolve() or not path.is_file():
        raise ValueError(f"Unknown fixture: {name}")
    return path


def fixture_uri(name: str) -> str:
    return fixture_path(name).as_uri()
