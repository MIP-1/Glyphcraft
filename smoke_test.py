from playwright.sync_api import sync_playwright
import os, json, base64

URL = "file:///home/mustafa/glyphcraft/index.html"
SHOT = "/tmp/glyphcraft_shots"
os.makedirs(SHOT, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    console = []
    errors = []
    page.on("console", lambda m: console.append((m.type, m.text)))
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(URL, wait_until="load")
    page.wait_for_timeout(500)
    page.screenshot(path=f"{SHOT}/empty_dark.png")

    page.set_input_files("#file-input", "/tmp/glyphcraft_test.png")
    page.wait_for_selector(".canvas-area.has-content", timeout=10000)
    page.wait_for_timeout(1500)
    status = page.inner_text("#status-bar")
    print("STATUS:", status)
    print("PANEL VISIBLE:", page.is_visible("#panel .panel-content"))
    page.screenshot(path=f"{SHOT}/loaded_dark.png")

    # light theme
    page.click("#menu-view")
    page.uncheck("#toggle-theme")
    page.wait_for_timeout(400)
    page.screenshot(path=f"{SHOT}/loaded_light.png")
    page.check("#toggle-theme")
    page.wait_for_timeout(300)

    # enable halftone
    page.check('.effect-item[data-id="halftone"] input[type="checkbox"]')
    page.wait_for_timeout(1200)
    page.screenshot(path=f"{SHOT}/halftone.png")

    # compare
    page.click("#menu-view")
    page.click('[data-action="compare"]')
    page.wait_for_timeout(800)
    page.screenshot(path=f"{SHOT}/compare.png")

    print("ERRORS:", json.dumps(errors))
    print("CONSOLE:", json.dumps([c for c in console if c[0] in ("error", "warning")]))
    print("EFFECT ITEMS:", page.locator(".effect-item").count())
    browser.close()
