#!/usr/bin/env python3
"""Run axe-core plus WAVE-style checks (tools/wave_lint.js) on every page, in light and dark themes.

  python3 -m http.server 8765   # in the project root, in another terminal
  python3 tools/check_pages.py  # needs: pip install playwright && Google Chrome installed
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8765/"
PAGES = ["index.html", "search.html", "search.html?q=golden+state+warirors", "404.html",
         "wiki/Golden_State_Warriors.html", "wiki/Stephen_Curry.html"]
LINT = (Path(__file__).parent / "wave_lint.js").read_text()
import urllib.request, ssl
try:
    import certifi
    _ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _ctx = None
AXE = urllib.request.urlopen("https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js", context=_ctx).read().decode()

failed = False
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    for theme in ("light", "dark"):
        ctx = browser.new_context(viewport={"width": 1400, "height": 900}, color_scheme=theme)
        for path in PAGES:
            page = ctx.new_page()
            # 404.html uses GitHub Pages' /my-awesome-site/ prefix; map it to the local server.
            page.route("**/my-awesome-site/**", lambda route: route.continue_(url=route.request.url.replace("/my-awesome-site/", "/")))
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_timeout(1500 if "q=" in path else 300)
            page.add_script_tag(content=AXE)
            page.add_script_tag(content=LINT)
            r = page.evaluate("waveLint()")
            bad = r["errors"] or r["contrastFails"] or r["axe"]
            failed |= bool(bad)
            alerts = {k: v.split(" e.g.")[0] for k, v in r["alerts"].items()}
            print(f"{'FAIL' if bad else 'ok  '} {theme:5} {path:40} errors={len(r['errors'])} contrast={r['contrastFails']} "
                  f"alerts={alerts} min={r['minContrast'][:28]}")
            if "possible heading" in r["alerts"]:
                print("       possible heading:", r["alerts"]["possible heading"][:300])
            if bad:
                print("      ", json.dumps({k: r[k] for k in ('errors', 'contrastSample', 'axe')}, indent=1)[:1500])
            page.close()
        ctx.close()
    browser.close()
sys.exit(1 if failed else 0)
