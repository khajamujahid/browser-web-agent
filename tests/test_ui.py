"""Drive the local UI and the static replay in Chromium."""

from __future__ import annotations

import functools
import http.server
import socket
import socketserver
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from webhands.goals import BOOK_GOAL, HN_GOAL
from webhands.server import app

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = Path("/opt/cursor/artifacts")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003 - stdlib signature
        return


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_app():
    import uvicorn

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while time.time() < deadline:
        if server.started:
            return server, thread, port
        time.sleep(0.05)
    raise RuntimeError("local UI did not start")


def _start_static(directory: Path):
    handler = functools.partial(_Quiet, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, httpd.server_address[1]


def _assert_fits(page, width: int) -> None:
    page.set_viewport_size({"width": width, "height": 800})
    box = page.locator("#run").bounding_box()
    assert box is not None and box["width"] > 40
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1


def test_local_ui_searches_the_bookstore():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    server, thread, port = _start_app()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/")
            page.wait_for_selector("#banner-local:not([hidden])")
            page.get_by_role("button", name="Python books under $30").click()
            assert page.input_value("#goal") == BOOK_GOAL
            page.click("#run")
            page.wait_for_selector("#result-table tbody tr")
            table = page.inner_text("#result-table")
            assert "Think Python" in table
            assert "Fluent Python" not in table
            log = page.inner_text("#steps")
            assert "Typed \"Python\"" in log
            assert "Submitted the search form." in log
            assert page.inner_text("#note")
            page.screenshot(path=str(ARTIFACTS / "webhands-local-books.png"), full_page=True)
            _assert_fits(page, 1280)
            _assert_fits(page, 390)
            page.screenshot(path=str(ARTIFACTS / "webhands-local-mobile.png"), full_page=True)
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_static_demo_replays_a_real_run_and_refuses_to_invent_one():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    httpd, thread, port = _start_static(ROOT / "demo")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/")
            page.wait_for_selector("#engine")
            page.wait_for_function("() => document.querySelector('#engine').textContent.includes('Recorded')")
            assert "cannot launch Playwright" in page.inner_text("#banner-demo")
            assert page.locator("#live").is_hidden()
            page.click("#run")
            page.wait_for_selector("#result-table tbody tr", timeout=15000)
            assert "Show HN: A browser agent that writes CSV, then stops" in page.inner_text("#result-table")
            assert "recorded offline run" in page.inner_text("#note")
            page.screenshot(path=str(ARTIFACTS / "webhands-demo-replay.png"), full_page=True)
            page.fill("#goal", "weather in Lisbon")
            page.click("#run")
            page.wait_for_selector("#note[data-kind=error]")
            assert "will not invent" in page.inner_text("#note")
            assert page.locator("#result-table").count() == 0
            _assert_fits(page, 390)
            browser.close()
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_package_ui_matches_the_demo_page():
    package = (ROOT / "src" / "webhands" / "ui" / "index.html").read_text(encoding="utf-8")
    demo = (ROOT / "demo" / "index.html").read_text(encoding="utf-8")
    assert package == demo
    assert HN_GOAL in package
    assert BOOK_GOAL in package
