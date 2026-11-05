"""URL and action gates for the optional LLM planner.

The rules planner never asks this module to open an arbitrary site. The LLM
planner may only open package fixtures or an allowlisted public host.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import unquote, urlparse

from webhands.errors import GoalError
from webhands.paths import FIXTURES_DIR, fixture_path, fixture_uri

ALLOWED_HOSTS = frozenset({"news.ycombinator.com"})
_DENY_SUFFIXES = (".local", ".internal", ".localhost")
_DENY_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata.google",
    }
)


def display_target(url: str) -> str:
    """Hide machine-specific file paths in step logs."""
    parsed = urlparse(url)
    if parsed.scheme == "file":
        try:
            path = _file_path(url)
            relative = path.resolve().relative_to(FIXTURES_DIR.resolve())
        except (ValueError, OSError):
            return "local file"
        return f"fixture:{relative.as_posix()}"
    return url


def resolve_url(url: str, *, offline: bool, extra_hosts: set[str] | None = None) -> tuple[str, str]:
    """Return (absolute url, short label) or raise GoalError."""
    if not isinstance(url, str) or not url.strip():
        raise GoalError("A goto action needs a URL.")
    raw = url.strip()
    if raw.startswith("fixture:"):
        name = raw.split(":", 1)[1].strip()
        try:
            path = fixture_path(name)
        except ValueError as exc:
            raise GoalError(str(exc)) from exc
        return path.as_uri(), f"fixture:{name}"

    parsed = urlparse(raw)
    if parsed.username or parsed.password:
        raise GoalError("URLs with credentials are not allowed.")
    if parsed.scheme == "file":
        path = _file_path(raw)
        root = FIXTURES_DIR.resolve()
        if path.resolve() != root and root not in path.resolve().parents:
            raise GoalError("File URL is outside the fixture directory.")
        if path.suffix.lower() not in {".html", ".htm"}:
            raise GoalError("Only HTML fixtures can be opened.")
        if not path.is_file():
            raise GoalError("Fixture file does not exist.")
        return path.as_uri(), display_target(path.as_uri())

    if offline:
        raise GoalError(
            "Offline mode only opens local fixtures. "
            "Pass --live to read the public Hacker News front page."
        )
    if parsed.scheme not in {"http", "https"}:
        raise GoalError("Only http(s) URLs are allowed.")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or not _host_allowed(host, extra_hosts or set()):
        raise GoalError(
            f"Host {host or '(missing)'} is not allowlisted. "
            "The default live host is news.ycombinator.com."
        )
    return raw, raw


def _file_path(url: str):
    from pathlib import Path

    parsed = urlparse(url)
    return Path(unquote(parsed.path))


def _host_allowed(host: str, extra_hosts: set[str]) -> bool:
    allowed = {item.lower().rstrip(".") for item in ALLOWED_HOSTS | set(extra_hosts)}
    if host not in allowed:
        return False
    if host in _DENY_HOSTS or host.endswith(_DENY_SUFFIXES):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return False
    return True


def fixture_page(name: str) -> str:
    """Convenience for recipes that already know the fixture name."""
    return fixture_uri(name)
