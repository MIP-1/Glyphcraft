from playwright.sync_api import sync_playwright
import os

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    console_msgs = []
    page_errors = []
    
    page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    
    file_path = f"file://{os.path.abspath('/home/mustafa/glyphcraft/index.html')}"
    page.goto(file_path, wait_until="networkidle")
    page.wait_for_timeout(2000)
    
    print("=== CONSOLE MESSAGES ===")
    for m in console_msgs:
        print(m)
    
    print("\n=== PAGE ERRORS ===")
    for e in page_errors:
        print(e)
    
    # Screenshot empty state
    page.screenshot(path="/tmp/glyphcraft_empty_dark.png", full_page=True)
    print("\nScreenshot saved to /tmp/glyphcraft_empty_dark.png")
    
    browser.close()