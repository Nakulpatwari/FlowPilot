"""Optional Playwright browser connector for a local, explicitly allowlisted sandbox.

The browser tool is not required for the core invoice path. It demonstrates how the
runtime can use browser automation without granting arbitrary Internet access.
"""
from urllib.parse import urlparse

ALLOWED_HOSTS = {"localhost", "127.0.0.1", "host.docker.internal"}

def inspect_local_page(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Browser tool only permits localhost/127.0.0.1/host.docker.internal URLs.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is optional. Install it with `pip install playwright` and `python -m playwright install chromium`.") from exc
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=8000)
        result = {
            "url": page.url,
            "title": page.title(),
            "visible_text": page.locator("body").inner_text(timeout=3000)[:5000],
        }
        browser.close()
        return result
