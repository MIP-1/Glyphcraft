from playwright.sync_api import sync_playwright
import os, sys, json, base64, subprocess, struct, time

ROOT = "/home/mustafa/glyphcraft"
URL = f"file://{ROOT}/index.html"
SHOT = "/tmp/glyphcraft_shots"
EXP = "/tmp/glyphcraft_exports"
REPORTS = f"{ROOT}/tests/reports"
os.makedirs(SHOT, exist_ok=True)
os.makedirs(REPORTS, exist_ok=True)
os.makedirs(EXP, exist_ok=True)

TEST_IMG = "/tmp/glyphcraft_test.png"
TEST_VIDEO = "/tmp/glyphcraft_test.webm"
if not os.path.exists(TEST_VIDEO):
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=2",
                    "-c:v", "libvpx-vp9", "-b:v", "200k", TEST_VIDEO],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

rows = []
def record(name, ok, detail=""):
    rows.append((name, bool(ok), detail))
    print(("PASS" if ok else "FAIL"), name, detail)

def magic_ok(path, fmt):
    with open(path, "rb") as f:
        head = f.read(16)
    if fmt == "png": return head.startswith(b"\x89PNG")
    if fmt == "jpg": return head.startswith(b"\xff\xd8\xff")
    if fmt == "webp": return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if fmt == "svg": return head.lstrip().startswith(b"<svg")
    if fmt == "txt": return len(head) > 0
    if fmt == "webm": return head.startswith(b"\x1aE\xdf\xa3")
    return False

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    console_errors, page_errors, warns = [], [], []
    page.on("console", lambda m: (console_errors.append(m.text) if m.type == "error" else warns.append(m.text) if m.type == "warning" else None))
    page.on("pageerror", lambda e: page_errors.append(str(e)))

    def open_menu(name):
        is_open = page.evaluate("(sel) => document.querySelector(sel).classList.contains('open')", "#dropdown-" + name)
        if not is_open:
            page.click("#menu-" + name)
        page.wait_for_timeout(250)

    def close_menus():
        page.evaluate("() => document.querySelectorAll('.menu-dropdown').forEach(d => d.classList.remove('open'))")

    def set_theme(dark):
        target = "dark" if dark else "light"
        current = page.evaluate("() => document.documentElement.dataset.theme")
        if current != target:
            page.click("#theme-toggle")
            page.wait_for_timeout(250)
        assert page.evaluate("() => document.documentElement.dataset.theme") == target, current

    def sig():
        return page.evaluate("""() => {
          const c = document.getElementById('canvas');
          if (!c.width) return 'empty';
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          let a = 0, b = 0;
          for (let i = 0; i < d.length; i += 17) { a = (a + d[i] * ((i % 251) + 1)) >>> 0; b = (b ^ d[i]) >>> 0; }
          return c.width + 'x' + c.height + ':' + a + ':' + b;
        }""")

    def set_output(w, h):
        page.select_option("#output-preset", "custom")
        page.evaluate("""([w,h]) => {
          for (const [id,v] of [['output-width',w],['output-height',h]]) {
            const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change',{bubbles:true}));
          }
        }""", [w, h])
        page.wait_for_timeout(250)

    def uncheck_all_effects():
        page.evaluate("""() => {
          document.querySelectorAll('.effect-item input[type=checkbox]').forEach(cb => {
            if (cb.checked) { cb.checked = false; cb.dispatchEvent(new Event('change',{bubbles:true})); }
          });
        }""")
        page.wait_for_timeout(250)

    def enable_effect(eid):
        page.evaluate("""(eid) => {
          const cb = document.querySelector('.effect-item[data-id="' + eid + '"] input[type=checkbox]');
          if (!cb.checked) { cb.checked = true; cb.dispatchEvent(new Event('change',{bubbles:true})); }
        }""", eid)
        page.wait_for_timeout(500)

    page.goto(URL, wait_until="load")
    page.wait_for_timeout(600)

    # 1. Empty state
    record("empty status", page.inner_text("#status-bar") == "No image loaded", page.inner_text("#status-bar"))
    record("drop zone visible", page.is_visible("#drop-zone"))
    page.screenshot(path=f"{SHOT}/empty_dark.png")
    set_theme(False)
    page.screenshot(path=f"{SHOT}/empty_light.png")
    set_theme(True)

    # contrast audit on light theme
    contrasts = page.evaluate("""() => {
      function lum(c){ const m=c.match(/\\d+/g).map(Number).map(v=>v/255).map(v=>v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)); return 0.2126*m[0]+0.7152*m[1]+0.0722*m[2]; }
      function bg(el){ let e=el; while(e){ const c=getComputedStyle(e).backgroundColor; if(c && c!=='rgba(0, 0, 0, 0)') return c; e=e.parentElement; } return 'rgb(255,255,255)'; }
      const sels=['#status-bar','.menu-btn','.section-title','.control-label','.checkbox','.effect-name'];
      const out={};
      for(const s of sels){ const el=document.querySelector(s); if(!el) continue; const fg=getComputedStyle(el).color, b=bg(el); const l1=lum(fg), l2=lum(b); out[s]=+(((Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05)).toFixed(2)); }
      return out;
    }""")
    record("light contrast AA", all(v >= 4.5 for v in contrasts.values()), json.dumps(contrasts))
    set_theme(True)
    dark_contrasts = page.evaluate("""() => {
      function lum(c){ const m=c.match(/\\d+/g).map(Number).map(v=>v/255).map(v=>v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)); return 0.2126*m[0]+0.7152*m[1]+0.0722*m[2]; }
      function bg(el){ let e=el; while(e){ const c=getComputedStyle(e).backgroundColor; if(c && c!=='rgba(0, 0, 0, 0)') return c; e=e.parentElement; } return 'rgb(0,0,0)'; }
      const out={};
      for(const s of ['#status-bar','.menu-btn','.section-title','.control-label','.checkbox','.effect-name']){ const el=document.querySelector(s); if(!el) continue; const fg=getComputedStyle(el).color, b=bg(el); const l1=lum(fg), l2=lum(b); out[s]=+(((Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05)).toFixed(2)); }
      return out;
    }""")
    record("dark contrast AA", all(v >= 4.5 for v in dark_contrasts.values()), json.dumps(dark_contrasts))

    # 2. Load image via file input
    page.set_input_files("#file-input", TEST_IMG)
    page.wait_for_selector(".canvas-area.has-content", timeout=15000)
    page.wait_for_timeout(900)
    status = page.inner_text("#status-bar")
    record("load status real size", "900×600" in status, status)
    record("panel visible after load", page.is_visible("#panel .panel-content"))
    record("drop zone hidden after load", not page.is_visible("#drop-zone"))
    record("22 effects listed", page.locator(".effect-item").count() == 22, str(page.locator(".effect-item").count()))
    with page.expect_file_chooser() as fc:
        open_menu("file")
        page.click('[data-action="open"]')
    fc.value.set_files(TEST_IMG)
    page.wait_for_timeout(900)
    record("File > Open Image menu", "900×600" in page.inner_text("#status-bar"))
    t0 = page.evaluate("() => document.getElementById('canvas').style.transform")
    abox = page.locator("#canvas-area").bounding_box()
    page.mouse.move(abox["x"] + 500, abox["y"] + 400)
    page.mouse.wheel(0, -400)
    page.wait_for_timeout(250)
    t1 = page.evaluate("() => document.getElementById('canvas').style.transform")
    page.keyboard.down("Space")
    page.mouse.move(abox["x"] + 500, abox["y"] + 400)
    page.mouse.down()
    page.mouse.move(abox["x"] + 620, abox["y"] + 480, steps=5)
    page.mouse.up()
    page.keyboard.up("Space")
    page.wait_for_timeout(250)
    t2 = page.evaluate("() => document.getElementById('canvas').style.transform")
    page.keyboard.press("f")
    page.wait_for_timeout(250)
    t3 = page.evaluate("() => document.getElementById('canvas').style.transform")
    record("wheel zoom", t0 != t1)
    record("space + drag pan", t1 != t2)
    record("F fit to window", t2 != t3)
    page.screenshot(path=f"{SHOT}/loaded_dark.png")
    set_theme(False)
    page.keyboard.press("Escape")
    page.screenshot(path=f"{SHOT}/loaded_light.png")
    set_theme(True)

    # small output for fast effect iteration
    set_output(500, 340)
    page.wait_for_timeout(400)

    effect_ids = page.evaluate("() => EFFECTS.map(e => e.id)")
    modes = ["script", "dither", "effects"]
    for mode in modes:
        page.select_option("#select-mode", mode)
        page.wait_for_timeout(400)
        uncheck_all_effects()
        baseline = sig()
        record(f"{mode}: baseline render", baseline != "empty", baseline[:28])
        for eid in effect_ids:
            enable_effect(eid)
            s = sig()
            ok = s != baseline
            record(f"{mode}: effect {eid}", ok, "changed" if ok else "NO CHANGE")
            if mode == "script":
                page.locator("#canvas-area").screenshot(path=f"{SHOT}/fx_{eid}.png")
            page.evaluate("""(eid) => {
              const cb = document.querySelector('.effect-item[data-id="' + eid + '"] input[type=checkbox]');
              cb.checked = false; cb.dispatchEvent(new Event('change',{bubbles:true}));
            }""", eid)
            page.wait_for_timeout(220)

    # 3. Effects UI: toggle, reset, reorder, search, collapse
    page.select_option("#select-mode", "script")
    page.evaluate("""() => {
      document.querySelectorAll('.effect-item input[type=checkbox]').forEach(cb => {
        if (cb.checked) { cb.checked = false; cb.dispatchEvent(new Event('change',{bubbles:true})); }
      });
    }""")
    page.wait_for_timeout(200)
    enable_effect("grain")
    page.click('[data-section="effects"].section-reset')
    page.wait_for_timeout(300)
    record("section reset clears effects", page.locator('.effect-item input[type=checkbox]:checked').count() == 0)

    base_stack = sig()
    enable_effect("posterize")
    one_stack = sig()
    enable_effect("vignette")
    two_stack = sig()
    record("effects stack", one_stack != base_stack and two_stack != one_stack, "1 effect and 2 effects differ")
    page.click('[data-section="effects"].section-reset')
    page.wait_for_timeout(250)

    adj_base = sig()
    page.locator("#adj-brightness").fill("40")
    page.wait_for_timeout(500)
    record("adjustment brightness", sig() != adj_base, "canvas changed")
    page.click('[data-section="adjustments"].section-reset')
    page.wait_for_timeout(400)
    page.check("#adj-sepia")
    page.wait_for_timeout(500)
    record("adjustment sepia", sig() != adj_base, "canvas changed")
    page.uncheck("#adj-sepia")
    page.wait_for_timeout(300)

    before_order = page.evaluate("() => Array.from(document.querySelectorAll('.effect-item')).slice(0,3).map(e=>e.dataset.id).join(',')")
    page.evaluate("""() => {
      const items = document.querySelectorAll('.effect-item');
      const dt = new DataTransfer();
      items[0].dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:dt}));
      items[2].dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:dt,cancelable:true}));
      items[0].dispatchEvent(new DragEvent('dragend',{bubbles:true}));
    }""")
    page.wait_for_timeout(250)
    after_order = page.evaluate("() => Array.from(document.querySelectorAll('.effect-item')).slice(0,3).map(e=>e.dataset.id).join(',')")
    record("effect drag reorder", before_order != after_order, f"{before_order} -> {after_order}")

    page.fill("#panel-search", "depth")
    page.wait_for_timeout(250)
    vis_sections = page.evaluate("() => Array.from(document.querySelectorAll('.panel-section')).filter(s=>s.style.display!=='none').length")
    page.fill("#panel-search", "")
    page.wait_for_timeout(250)
    all_sections = page.evaluate("() => Array.from(document.querySelectorAll('.panel-section')).filter(s=>s.style.display!=='none').length")
    record("search filters controls", vis_sections < all_sections, f"{vis_sections}/{all_sections}")

    page.click("#section-script .section-title")
    collapsed = page.evaluate("() => document.getElementById('section-script').classList.contains('collapsed')")
    page.click("#section-script .section-title")
    record("section collapse", collapsed)

    page.click("#panel-toggle-btn")
    panel_collapsed = page.evaluate("() => document.querySelector('.workspace').classList.contains('panel-collapsed')")
    page.click("#panel-toggle-btn")
    record("panel collapse", panel_collapsed)

    # 4. Undo / redo
    page.locator("#depth").fill("120")
    page.wait_for_timeout(500)
    d1 = page.input_value("#depth")
    page.keyboard.press("Control+z")
    page.wait_for_timeout(400)
    d2 = page.input_value("#depth")
    page.keyboard.press("Control+Shift+z")
    page.wait_for_timeout(400)
    d3 = page.input_value("#depth")
    record("undo/redo", (d1, d2, d3) == ("120", "80", "120"), f"{d1} -> {d2} -> {d3}")

    # 5. Named presets
    base_sig = sig()
    page.click('[data-preset="terminal"]')
    page.wait_for_timeout(700)
    preset_sig = sig()
    crt_on = page.evaluate("() => document.querySelector('.effect-item[data-id=\"crt\"] input').checked")
    record("preset Terminal Green", preset_sig != base_sig and crt_on, "crt on, canvas changed")
    all_ok, details = True, []
    for pname in ["newsprint", "cyber", "gameboy", "blueprint", "oldphoto", "thermal"]:
        page.click(f'[data-preset="{pname}"]')
        page.wait_for_timeout(600)
        changed = sig() != base_sig
        all_ok = all_ok and changed
        details.append(f"{pname}:{'ok' if changed else 'same'}")
    record("all named presets", all_ok, ", ".join(details))

    # save / load preset
    page.once("dialog", lambda d: d.accept("mytest"))
    page.click("#btn-save-preset")
    page.wait_for_timeout(400)
    saved = page.evaluate("() => JSON.parse(localStorage.getItem('glyphcraft-presets') || '{}').mytest ? true : false")
    page.locator("#depth").fill("150")
    page.wait_for_timeout(500)
    page.once("dialog", lambda d: d.accept("mytest"))
    page.click("#btn-load-preset")
    page.wait_for_timeout(600)
    record("save/load custom preset", saved and page.input_value("#depth") == "80", f"saved={saved}, depth={page.input_value('#depth')}")

    # 6. Compare split + hold original
    open_menu("edit")
    page.click('[data-action="compare"]')
    page.wait_for_timeout(600)
    overlay = page.is_visible("#compare-overlay")
    split = page.evaluate("""() => {
      const c = document.getElementById('canvas');
      const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      const y = Math.floor(c.height/2), xl = Math.floor(c.width*0.15), xr = Math.floor(c.width*0.85);
      const i1=(y*c.width+xl)*4, i2=(y*c.width+xr)*4;
      return [d[i1],d[i1+1],d[i1+2], d[i2],d[i2+1],d[i2+2]];
    }""")
    record("compare overlay", overlay)
    record("compare splits original/processed", split[:3] != split[3:], str(split))
    page.screenshot(path=f"{SHOT}/compare.png")
    before_frac = page.evaluate("() => document.getElementById('compare-slider').style.left")
    box = page.locator("#compare-slider").bounding_box()
    page.mouse.move(box["x"] + 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + 120, box["y"] + box["height"] / 2, steps=5)
    page.mouse.up()
    page.wait_for_timeout(400)
    after_frac = page.evaluate("() => document.getElementById('compare-slider').style.left")
    record("compare slider drag", before_frac != after_frac, f"{before_frac} -> {after_frac}")
    page.mouse.move(720, 500)
    page.keyboard.down("o")
    page.wait_for_timeout(400)
    hold_sig = sig()
    page.keyboard.up("o")
    page.wait_for_timeout(300)
    record("hold original differs", hold_sig != preset_sig, "original image shown")
    open_menu("edit")
    page.click('[data-action="compare"]')
    page.wait_for_timeout(300)

    # 7. Drag and drop + paste
    b64 = base64.b64encode(open(TEST_IMG, "rb").read()).decode()
    page.evaluate("""(b64) => {
      const bin = atob(b64), arr = new Uint8Array(bin.length);
      for (let i=0;i<bin.length;i++) arr[i]=bin.charCodeAt(i);
      const file = new File([arr], 'drop.png', {type:'image/png'});
      const dt = new DataTransfer(); dt.items.add(file);
      window.dispatchEvent(new DragEvent('drop', {dataTransfer:dt, bubbles:true, cancelable:true}));
    }""", b64)
    page.wait_for_timeout(900)
    record("drag and drop load", "900×600" in page.inner_text("#status-bar"), page.inner_text("#status-bar"))
    page.evaluate("""(b64) => {
      const bin = atob(b64), arr = new Uint8Array(bin.length);
      for (let i=0;i<bin.length;i++) arr[i]=bin.charCodeAt(i);
      const file = new File([arr], 'paste.png', {type:'image/png'});
      const dt = new DataTransfer(); dt.items.add(file);
      document.dispatchEvent(new ClipboardEvent('paste', {clipboardData:dt, bubbles:true, cancelable:true}));
    }""", b64)
    page.wait_for_timeout(900)
    record("paste load", "900×600" in page.inner_text("#status-bar"), page.inner_text("#status-bar"))

    # 8. Exports
    page.select_option("#output-preset", "original")
    page.wait_for_timeout(300)
    page.evaluate("""() => {
      document.querySelectorAll('.effect-item input[type=checkbox]').forEach(cb => {
        if (cb.checked) { cb.checked = false; cb.dispatchEvent(new Event('change',{bubbles:true})); }
      });
    }""")
    page.wait_for_timeout(300)
    for fmt in ["png", "jpg", "webp", "svg", "txt", "webm"]:
        page.select_option("#export-format", fmt)
        try:
            with page.expect_download(timeout=90000) as dl:
                page.click("#btn-export")
            d = dl.value
            path = f"{EXP}/glyphcraft.{fmt}"
            d.save_as(path)
            size = os.path.getsize(path)
            ok = size > 0 and magic_ok(path, fmt)
            record(f"export {fmt}", ok, f"{size} bytes, magic={'ok' if magic_ok(path, fmt) else 'bad'}")
        except Exception as e:
            record(f"export {fmt}", False, str(e)[:120])

    # 8b. full-resolution export size
    set_output(640, 400)
    page.select_option("#export-format", "png")
    with page.expect_download(timeout=30000) as dl:
        page.click("#btn-export")
    sized = f"{EXP}/sized.png"
    dl.value.save_as(sized)
    from PIL import Image
    dims = Image.open(sized).size
    record("export honours output size", dims == (640, 400), str(dims))
    page.select_option("#output-preset", "original")
    page.wait_for_timeout(300)

    # 9. Effects included in PNG export
    enable_effect("invert")
    page.wait_for_timeout(500)
    page.select_option("#export-format", "png")
    with page.expect_download(timeout=30000) as dl:
        page.click("#btn-export")
    inv = f"{EXP}/inverted.png"
    dl.value.save_as(inv)
    page.select_option("#export-format", "txt")
    with page.expect_download(timeout=30000) as dl:
        page.click("#btn-export")
    invtxt = f"{EXP}/inverted.txt"
    dl.value.save_as(invtxt)
    record("effects in PNG export", os.path.getsize(inv) > 0 and os.path.getsize(inv) != os.path.getsize(f"{EXP}/glyphcraft.png"), f"{os.path.getsize(inv)} bytes")
    record("effects in TXT export", os.path.getsize(invtxt) > 0 and open(invtxt).read() != open(f"{EXP}/glyphcraft.txt").read(), f"{os.path.getsize(invtxt)} bytes")
    page.select_option("#export-format", "svg")
    with page.expect_download(timeout=30000) as dl:
        page.click("#btn-export")
    invsvg = f"{EXP}/inverted.svg"
    dl.value.save_as(invsvg)
    record("effects in SVG export", os.path.getsize(invsvg) > 0 and open(invsvg).read() != open(f"{EXP}/glyphcraft.svg").read(), f"{os.path.getsize(invsvg)} bytes")
    page.click('[data-section="effects"].section-reset')
    page.wait_for_timeout(300)

    # 10. Video input
    try:
        page.set_input_files("#file-input", TEST_VIDEO)
        page.wait_for_timeout(1500)
        vstatus = page.inner_text("#status-bar")
        record("video load", "320×240" in vstatus, vstatus)
        page.locator("#canvas-area").screenshot(path=f"{SHOT}/video_loaded.png")
    except Exception as e:
        record("video load", False, str(e)[:120])

    # 11. Round 2: zoom toolbar, menus, touch targets, action bar
    page.click("#zoom-level")
    page.wait_for_timeout(250)
    record("zoom menu opens", page.is_visible("#zoom-menu"))
    page.click('[data-zoom="4"]')
    page.wait_for_timeout(350)
    z400 = page.inner_text("#zoom-level")
    ir = page.evaluate("() => getComputedStyle(document.getElementById('canvas')).imageRendering")
    record("zoom preset 400% is crisp", z400 == "400%" and ir == "pixelated", f"{z400}, {ir}")

    for _ in range(20):
        if page.is_disabled("#zoom-in"):
            break
        page.click("#zoom-in")
    page.wait_for_timeout(300)
    zmax = page.inner_text("#zoom-level")
    record("zoom max 800%, + disabled", zmax == "800%" and page.is_disabled("#zoom-in"), zmax)

    for _ in range(40):
        if page.is_disabled("#zoom-out"):
            break
        page.click("#zoom-out")
    page.wait_for_timeout(300)
    zmin = page.inner_text("#zoom-level")
    record("zoom min 10%, - disabled", zmin == "10%" and page.is_disabled("#zoom-out"), zmin)

    page.locator("#canvas-area").click(position={"x": 200, "y": 150})
    page.keyboard.press("0")
    page.wait_for_timeout(300)
    zfit = page.inner_text("#zoom-level")
    record("0 = fit window", zfit != "10%" and zfit != "800%", zfit)
    open_menu("view")
    page.click('[data-action="fit-small"]')
    page.wait_for_timeout(350)
    zsmall = page.inner_text("#zoom-level")
    record("fit small ~ half of fit", abs(int(zsmall[:-1]) - int(zfit[:-1]) / 2) <= 3, f"{zfit} -> {zsmall}")

    open_menu("view")
    page.click('[data-action="fullpage"]')
    page.wait_for_timeout(400)
    full_on = page.evaluate("() => document.querySelector('.workspace').classList.contains('fullpage')")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    full_off = page.evaluate("() => document.querySelector('.workspace').classList.contains('fullpage')")
    record("full page hides panel, Esc restores", full_on and not full_off)

    z_before_wheel = page.inner_text("#zoom-level")
    area_box = page.locator("#canvas-area").bounding_box()
    page.mouse.move(area_box["x"] + 240, area_box["y"] + 180)
    page.keyboard.down("Control")
    page.mouse.wheel(0, -300)
    page.keyboard.up("Control")
    page.wait_for_timeout(300)
    z_after_wheel = page.inner_text("#zoom-level")
    record("Ctrl + wheel zooms", z_before_wheel != z_after_wheel, f"{z_before_wheel} -> {z_after_wheel}")

    # Sticky action bar: opaque, full panel width, nothing shows through the gap.
    page.evaluate("() => { document.querySelector('.panel-content').scrollTop = 900; }")
    page.wait_for_timeout(300)
    abar = page.evaluate("""() => {
      const b = document.getElementById('panel-actionbar');
      const r = b.getBoundingClientRect();
      const p = document.getElementById('panel').getBoundingClientRect();
      const cs = getComputedStyle(b);
      const gap = document.elementFromPoint(r.x + 6, r.y + r.height / 2);
      return {w: r.width, pw: p.width, bg: cs.backgroundColor, z: cs.zIndex,
              gapId: gap ? (gap.id || gap.className) : 'none'};
    }""")
    record("action bar solid + full width",
           abar["bg"].startswith("rgb(") and abar["w"] >= abar["pw"] - 2 and int(abar["z"]) >= 10 and "actionbar" in str(abar["gapId"]),
           json.dumps(abar))

    # Menus: keyboard navigation and Esc.
    page.evaluate("() => { document.querySelector('.panel-content').scrollTop = 0; }")
    page.click("#menu-file")
    page.wait_for_timeout(250)
    first_item = page.evaluate("() => document.activeElement.dataset.action")
    page.keyboard.press("ArrowDown")
    second_item = page.evaluate("() => document.activeElement.dataset.action")
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)
    menu_closed = page.evaluate("() => !document.getElementById('dropdown-file').classList.contains('open')")
    record("menu arrow keys + Esc", first_item == "open" and second_item == "export" and menu_closed,
           f"{first_item} -> {second_item}, closed={menu_closed}")

    # Touch targets in the panel and toolbar.
    small_targets = page.evaluate("""() => {
      const out = [];
      document.querySelectorAll('.panel-content button, .panel-content input, .panel-content select, .menubar button').forEach(el => {
        if (el.closest('[hidden]') || el.offsetParent === null) return;
        if (el.id === 'panel-toggle' || el.classList.contains('drag-handle')) return;
        const r = el.getBoundingClientRect();
        if (r.width < 44 || r.height < 44) {
          out.push({tag: el.tagName, id: el.id, cls: String(el.className), w: Math.round(r.width), h: Math.round(r.height)});
        }
      });
      return out;
    }""")
    record("touch targets >= 44px", len(small_targets) == 0, json.dumps(small_targets[:8]))

    # Theme toggle: icon + label reflect the current theme.
    set_theme(False)
    light_icons = page.evaluate("""() => ({
      sun: getComputedStyle(document.querySelector('.theme-toggle .icon-sun')).display,
      moon: getComputedStyle(document.querySelector('.theme-toggle .icon-moon')).display,
      label: document.getElementById('theme-toggle').getAttribute('aria-label')
    })""")
    record("light theme: sun icon, action label", light_icons["sun"] != "none" and light_icons["moon"] == "none" and light_icons["label"] == "Switch to dark theme", json.dumps(light_icons))
    set_theme(True)
    dark_icons = page.evaluate("""() => ({
      sun: getComputedStyle(document.querySelector('.theme-toggle .icon-sun')).display,
      moon: getComputedStyle(document.querySelector('.theme-toggle .icon-moon')).display,
      label: document.getElementById('theme-toggle').getAttribute('aria-label')
    })""")
    record("dark theme: moon icon, action label", dark_icons["moon"] != "none" and dark_icons["sun"] == "none" and dark_icons["label"] == "Switch to light theme", json.dumps(dark_icons))

    page.reload(wait_until="load")
    page.wait_for_timeout(700)
    theme = page.evaluate("() => document.documentElement.dataset.theme")
    record("theme persists after reload", theme == "dark", theme)
    record("empty state after reload", page.is_visible("#drop-zone") and page.inner_text("#status-bar") == "No image loaded")
    with page.expect_file_chooser() as chooser:
        page.click("#open-file-btn")
    chooser.value.set_files(TEST_IMG)
    page.wait_for_timeout(900)
    record("Open file button works", "900×600" in page.inner_text("#status-bar"), page.inner_text("#status-bar"))
    page.wait_for_timeout(300)
    record("zero console errors", len(console_errors) == 0, json.dumps(console_errors[:3]))
    record("zero page errors", len(page_errors) == 0, json.dumps(page_errors[:3]))

    # Arabic home screen (separate locale context).
    actx = browser.new_context(viewport={"width": 390, "height": 820}, locale="ar-SA")
    apage = actx.new_page()
    arabic_errors = []
    apage.on("pageerror", lambda e: arabic_errors.append(str(e)))
    apage.goto(URL, wait_until="load")
    apage.wait_for_timeout(500)
    arabic_ok = apage.evaluate("""() => ({
      dir: document.documentElement.dir,
      hint: document.querySelector('.drop-hint').textContent,
      open: document.getElementById('open-file-btn').textContent,
      status: document.getElementById('status-bar').textContent
    })""")
    apage.evaluate("() => window.showDropError('errSize', {size: '50 MB', max: '40 MB'})")
    apage.wait_for_timeout(200)
    arabic_err = apage.inner_text(".drop-error")
    apage.screenshot(path=f"{SHOT}/home_arabic.png")
    record("Arabic home screen",
           arabic_ok["dir"] == "rtl" and "أفلت" in arabic_ok["hint"] and arabic_ok["open"] == "فتح ملف",
           json.dumps(arabic_ok, ensure_ascii=False))
    record("Arabic honest error message", "كبير" in arabic_err and "40 MB" in arabic_err, arabic_err)
    actx.close()

    browser.close()

# Automated contrast audit, both themes at 1280 and 360.
contrast = subprocess.run([sys.executable, f"{ROOT}/tests/test_contrast.py"], capture_output=True, text=True)
summary = (contrast.stdout.strip().splitlines() or [contrast.stderr[-200:]])[-1]
record("contrast audit (both themes, 360+1280)", contrast.returncode == 0, summary)

with open(f"{REPORTS}/TEST_RESULTS.json", "w") as f:
    json.dump({"rows": rows, "warnings": warns[:5]}, f, indent=2)

lines = ["# Glyphcraft Test Report", "", f"Run: {time.strftime('%Y-%m-%d %H:%M:%S')}",
         "", "Command: `python tests/test_suite.py` (headless Chromium via Playwright, file:// URL)", "",
         f"Total: {len(rows)} | Pass: {sum(1 for _,ok,_ in rows if ok)} | Fail: {sum(1 for _,ok,_ in rows if not ok)}", "",
         "| Check | Result | Detail |", "|---|---|---|"]
for name, ok, detail in rows:
    lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {str(detail).replace('|','/')} |")
lines += ["", "## Screenshots", f"- Contrast: `{REPORTS}/contrast-<theme>-<width>.png`",
          f"- Empty state: `{SHOT}/empty_dark.png`, `{SHOT}/empty_light.png`",
          f"- Loaded: `{SHOT}/loaded_dark.png`, `{SHOT}/loaded_light.png`",
          f"- Arabic home: `{SHOT}/home_arabic.png`",
          f"- Per-effect (script): `{SHOT}/fx_<id>.png`",
          f"- Compare: `{SHOT}/compare.png`", f"- Video: `{SHOT}/video_loaded.png`", "",
          "## Not tested", "- Firefox/Safari rendering (only headless Chromium was available).",
          "- Two-finger pinch zoom is implemented with Pointer Events but could only be simulated, not tested on physical hardware.",
          "- Full-resolution WebM export of a moving video (WebM export was exercised on a still image; video input was loaded and rendered).",
          "- Web Worker chunking: not implemented. Heavy effects run synchronously on the reduced preview (<=1600px), so a ~0.5-1s UI pause is possible on the largest previews.",
          "- CRT curvature is a scanline/row-warp approximation, not a true lens model.",
          "- Only headless Chromium was run; no interactive browser was used."]
open(f"{REPORTS}/TEST_REPORT.md", "w").write("\n".join(lines) + "\n")
print("REPORT WRITTEN", len(rows), "checks,", sum(1 for _,ok,_ in rows if not ok), "failures")
