"""
Render docs/architecture.html to docs/architecture.png.

    uv run --no-project --with playwright python docs/render_architecture.py

Uses the locally installed Microsoft Edge (channel="msedge"); on other systems run
`playwright install chromium` once and change the channel to None.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge")
    page = browser.new_page(viewport={"width": 2840, "height": 1880}, device_scale_factor=1.5)
    page.goto((HERE / "architecture.html").as_uri())
    page.wait_for_selector("body[data-ready='1']")
    page.locator("#canvas").screenshot(path=str(HERE / "architecture.png"))
    browser.close()
print(f"Saved {HERE / 'architecture.png'}")
