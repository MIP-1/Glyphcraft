#!/usr/bin/env python3
"""Does this Firefox emit PerformanceObserver 'longtask' entries?"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.firefox.launch(headless=True)
    page = b.new_page()
    page.goto("about:blank")
    supported = page.evaluate("() => PerformanceObserver.supportedEntryTypes || []")
    got = page.evaluate("""() => new Promise((resolve) => {
      const seen = [];
      try {
        new PerformanceObserver((l) => { for (const e of l.getEntries()) seen.push(e.duration); })
          .observe({ entryTypes: ["longtask"] });
      } catch (e) { resolve({error: String(e), seen}); return; }
      const t0 = performance.now();
      while (performance.now() - t0 < 120) {}
      setTimeout(() => resolve({seen, supported: PerformanceObserver.supportedEntryTypes}), 300);
    })""")
    print("supportedEntryTypes:", supported)
    print("probe:", got)
    print("version:", b.version)
    b.close()
