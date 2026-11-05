"""Playwright session and the fixed extractors the agent is allowed to use."""

from __future__ import annotations

import re

from webhands.errors import AgentError

HN_COLUMNS = ["rank", "title", "url", "points", "comments"]
BOOK_COLUMNS = ["title", "author", "price", "format"]
LINK_COLUMNS = ["title", "url"]
HEADING_COLUMNS = ["level", "text"]

_HN_JS = """
() => {
  const stories = [];
  document.querySelectorAll("tr.athing").forEach((row) => {
    const link = row.querySelector("span.titleline > a");
    if (!link) return;
    const rank = (row.querySelector(".rank")?.textContent || "").trim();
    const sub = row.nextElementSibling;
    const score = sub?.querySelector(".score")?.textContent || "";
    const commentLink = sub
      ? Array.from(sub.querySelectorAll("a")).find((anchor) =>
          /comment|discuss/i.test(anchor.textContent || "")
        )
      : null;
    stories.push({
      rank,
      title: (link.textContent || "").trim(),
      url: link.getAttribute("href") || "",
      points: score,
      comments: commentLink ? commentLink.textContent || "" : "",
    });
  });
  return stories;
}
"""

_BOOK_JS = """
() => {
  const books = [];
  document.querySelectorAll("article.book").forEach((book) => {
    if (book.classList.contains("is-hidden")) return;
    books.push({
      title: book.dataset.title || "",
      author: book.dataset.author || "",
      price: book.dataset.price || "",
      format: book.dataset.format || "",
    });
  });
  return books;
}
"""

_LINK_JS = """
() => Array.from(document.querySelectorAll("a[href]"))
  .map((anchor) => ({
    title: (anchor.textContent || "").trim(),
    url: anchor.getAttribute("href") || "",
  }))
  .filter((item) => item.title && item.url && !item.url.startsWith("#"))
  .slice(0, 30)
"""

_HEADING_JS = """
() => Array.from(document.querySelectorAll("h1, h2, h3"))
  .map((heading) => ({
    level: heading.tagName.toLowerCase(),
    text: (heading.textContent || "").trim(),
  }))
  .filter((item) => item.text)
  .slice(0, 50)
"""


class BrowserSession:
    """One Chromium window. Use as a context manager so the browser always closes."""

    def __init__(self, *, headless: bool = True) -> None:
        self.headless = headless
        self._playwright = None
        self._browser = None
        self.page = None

    def __enter__(self) -> "BrowserSession":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise AgentError(
                "Playwright is not installed. Run: python -m pip install -e . "
                "&& python -m playwright install chromium"
            ) from exc
        try:
            self._playwright = sync_playwright().start()
            # Container and CI hosts block the Chromium sandbox; these flags are the
            # supported way to launch there. Local desktops tolerate them too.
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = self._browser.new_context(
                viewport={"width": 1100, "height": 900},
                user_agent=(
                    "WebHands/0.1 (educational demo; "
                    "+https://github.com/khajamujahid/browser-web-agent)"
                ),
            )
            self.page = context.new_page()
            self.page.set_default_timeout(15_000)
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self.page = None

    def goto(self, url: str) -> str:
        assert self.page is not None
        self.page.goto(url, wait_until="domcontentloaded")
        return self.page.title()

    def fill(self, selector: str, text: str) -> None:
        assert self.page is not None
        self.page.fill(selector, text)

    def click(self, selector: str) -> None:
        assert self.page is not None
        self.page.click(selector)

    def press(self, selector: str, key: str) -> None:
        assert self.page is not None
        self.page.press(selector, key)

    def wait(self, selector: str) -> None:
        assert self.page is not None
        self.page.wait_for_selector(selector)

    def extract(self, mode: str) -> tuple[list[str], list[dict]]:
        if mode == "hn_stories":
            return HN_COLUMNS, [_normalize_story(item, index) for index, item in enumerate(self._eval(_HN_JS), start=1)]
        if mode == "books":
            return BOOK_COLUMNS, list(self._eval(_BOOK_JS))
        if mode == "links":
            return LINK_COLUMNS, list(self._eval(_LINK_JS))
        if mode == "headings":
            return HEADING_COLUMNS, list(self._eval(_HEADING_JS))
        raise AgentError(f"Unknown extract mode: {mode}")

    def _eval(self, script: str):
        assert self.page is not None
        return self.page.evaluate(script)


def _normalize_story(item: dict, index: int) -> dict:
    rank_text = str(item.get("rank", "")).rstrip(".")
    rank = int(rank_text) if rank_text.isdigit() else index
    return {
        "rank": rank,
        "title": str(item.get("title", "")).strip(),
        "url": str(item.get("url", "")).strip(),
        "points": _first_int(str(item.get("points", ""))),
        "comments": _first_int(str(item.get("comments", ""))),
    }


def _first_int(text: str) -> int:
    match = re.search(r"\d+", text or "")
    return int(match.group()) if match else 0


def explain_browser_error(exc: Exception) -> str:
    message = str(exc)
    if "Executable doesn't exist" in message or "playwright install" in message:
        return "Chromium is not installed. Run: python -m playwright install chromium"
    if "Timeout" in message and "waiting for" in message:
        return "The page did not show the element the agent tried to use."
    return message.splitlines()[0][:300]
