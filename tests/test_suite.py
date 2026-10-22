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

    def effect_param(eid):
        return page.evaluate("""(eid) => {
          const item = document.querySelector('.effect-item[data-id="' + eid + '"]');
          const n = item.querySelector('.param input[type=number]');
          const s = item.querySelector('.param input[type=range]');
          const def = EFFECTS.find(e => e.id === eid).params.find(p => p.type !== 'color' && p.type !== 'select');
          return {key: def.key, min: def.min, max: def.max, step: def.step, def: def.def,
                  number: +n.value, raw: n.value, slider: +s.value,
                  state: state.opts.effects.find(e => e.id === eid).params[def.key]};
        }""", eid)

    def set_effect_number(eid, value):
        page.evaluate("""([eid, value]) => {
          const n = document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=number]');
          n.focus();
          n.value = String(value);
          n.dispatchEvent(new Event('input', {bubbles:true}));
        }""", [eid, value])

    def set_effect_slider(eid, value):
        page.evaluate("""([eid, value]) => {
          const s = document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=range]');
          s.value = value;
          s.dispatchEvent(new Event('input', {bubbles:true}));
        }""", [eid, value])

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

    # Round 1 Tasks 2/3: effect values survive editing, stay synced, and re-render.
    param_effects = ["halftone", "crt", "glitch", "pixelate", "vignette"]
    slider_sync, slider_render, typing_sync = [], [], []
    arrow_exact, wheel_step, empty_ok, clamp_ok = [], [], [], []
    hold_ok, drag_ok = [], []
    for eid in param_effects:
        enable_effect(eid)
        info = effect_param(eid)
        target = info["min"] + info["step"] * 2

        before = sig()
        set_effect_slider(eid, info["max"])
        page.wait_for_timeout(300)
        after_slider = effect_param(eid)
        slider_sync.append(after_slider["number"] == info["max"] and after_slider["slider"] == info["max"])
        slider_render.append(sig() != before)

        set_effect_number(eid, target)
        page.wait_for_timeout(300)
        after_type = effect_param(eid)
        typing_sync.append(after_type["number"] == target and after_type["slider"] == target and after_type["state"] == target)

        page.evaluate("""(eid) => document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=number]').focus()""", eid)
        page.keyboard.press("ArrowUp")
        page.wait_for_timeout(180)
        up = effect_param(eid)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(180)
        down = effect_param(eid)
        arrow_exact.append(up["number"] == target + info["step"] and down["number"] == target and down["state"] == target)

        page.evaluate("""(eid) => {
          const n = document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=number]');
          n.focus();
          for (let i = 0; i < 3; i++) {
            n.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowUp', bubbles:true, cancelable:true, repeat:i > 0}));
          }
        }""", eid)
        page.wait_for_timeout(300)
        held = effect_param(eid)
        page.evaluate("""(eid) => {
          const n = document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=number]');
          n.focus();
          for (let i = 0; i < 3; i++) {
            n.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown', bubbles:true, cancelable:true, repeat:i > 0}));
          }
        }""", eid)
        page.wait_for_timeout(300)
        settled = effect_param(eid)
        hold_ok.append(held["number"] == target + info["step"] * 3 and held["state"] == target + info["step"] * 3 and settled["number"] == target and settled["state"] == target)

        page.evaluate("""(eid) => {
          const n = document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=number]');
          n.focus();
          n.dispatchEvent(new WheelEvent('wheel', {deltaY:-100, bubbles:true, cancelable:true}));
        }""", eid)
        page.wait_for_timeout(220)
        wheel = effect_param(eid)
        wheel_step.append(wheel["number"] == target + info["step"] and wheel["state"] == target + info["step"])

        page.evaluate("""(eid) => {
          const n = document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=number]');
          n.focus();
          n.value = '';
          n.dispatchEvent(new Event('input', {bubbles:true}));
        }""", eid)
        page.wait_for_timeout(180)
        empty = effect_param(eid)
        page.evaluate("""(eid) => document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=number]').blur()""", eid)
        page.wait_for_timeout(220)
        restored = effect_param(eid)
        empty_ok.append(empty["raw"] == "" and empty["state"] == target + info["step"] and restored["number"] == target + info["step"])

        page.evaluate("""(eid) => {
          const n = document.querySelector('.effect-item[data-id="' + eid + '"] .param input[type=number]');
          n.focus();
          n.value = String(+n.max + 10);
          n.dispatchEvent(new Event('input', {bubbles:true}));
          n.blur();
        }""", eid)
        page.wait_for_timeout(240)
        clamped = effect_param(eid)
        clamp_ok.append(clamped["number"] == info["max"] and clamped["state"] == info["max"])

        slider_loc = page.locator(f'.effect-item[data-id="{eid}"] .param input[type=range]').first
        slider_loc.scroll_into_view_if_needed()
        page.wait_for_timeout(120)
        sb = slider_loc.bounding_box()
        page.mouse.move(sb["x"] + sb["width"] - 5, sb["y"] + sb["height"] / 2)
        page.mouse.down()
        page.mouse.move(sb["x"] + 6, sb["y"] + sb["height"] / 2, steps=10)
        page.mouse.up()
        page.wait_for_timeout(350)
        dragged = effect_param(eid)
        drag_ok.append(dragged["number"] == dragged["slider"] and dragged["state"] == dragged["number"] and dragged["number"] < info["max"])

        page.evaluate("""(eid) => {
          const cb = document.querySelector('.effect-item[data-id="' + eid + '"] input[type=checkbox]');
          cb.checked = false; cb.dispatchEvent(new Event('change', {bubbles:true}));
        }""", eid)
        page.wait_for_timeout(180)

    all_params = page.evaluate("""() => {
      const failures = [];
      let count = 0;
      for (const fx of state.opts.effects) {
        const def = EFFECTS.find(e => e.id === fx.id);
        if (!def) continue;
        const item = document.querySelector('.effect-item[data-id="' + fx.id + '"]');
        const nums = Array.from(item.querySelectorAll('.param input[type=number]'));
        let ni = 0;
        for (const p of def.params) {
          if (p.type === 'color' || p.type === 'select') continue;
          const n = nums[ni++];
          if (!n) { failures.push(fx.id + '.' + p.key + ': no input'); continue; }
          let target = p.min + p.step * 2;
          if (target > p.max - p.step) target = p.min + p.step;
          n.focus(); n.value = String(target);
          n.dispatchEvent(new Event('input', {bubbles:true})); n.blur();
          const before = fx.params[p.key];
          n.focus();
          n.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowUp', bubbles:true, cancelable:true}));
          n.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowDown', bubbles:true, cancelable:true}));
          const after = fx.params[p.key];
          if (before !== after || Number(n.value) !== after) failures.push(fx.id + '.' + p.key + ': step ' + before + '->' + after + ' field=' + n.value);
          n.focus(); n.value = String(p.max + p.step * 10);
          n.dispatchEvent(new Event('input', {bubbles:true})); n.blur();
          if (fx.params[p.key] !== p.max) failures.push(fx.id + '.' + p.key + ': max ' + fx.params[p.key] + ' != ' + p.max);
          n.focus(); n.value = String(p.min - p.step * 10);
          n.dispatchEvent(new Event('input', {bubbles:true})); n.blur();
          if (fx.params[p.key] !== p.min) failures.push(fx.id + '.' + p.key + ': min ' + fx.params[p.key] + ' != ' + p.min);
          count++;
        }
      }
      return {failures, count};
    }""")
    precision = page.evaluate("() => ({a: roundToStep(0.1 + 0.2, 0.1, 0), b: roundToStep(1.05, 0.1, 0)})")
    record("effect slider sync + render (5 effects)", all(slider_sync) and all(slider_render),
           f"sync={slider_sync}, render={slider_render}")
    record("effect number typing sync (5 effects)", all(typing_sync), str(typing_sync))
    record("effect arrows exact one step (5 effects)", all(arrow_exact), str(arrow_exact))
    record("effect hold repeats one step (5 effects)", all(hold_ok), str(hold_ok))
    record("effect slider mouse drag sync (5 effects)", all(drag_ok), str(drag_ok))
    record("effect wheel exact one step (5 effects)", all(wheel_step), str(wheel_step))
    record("effect empty typing preserved (5 effects)", all(empty_ok), str(empty_ok))
    record("effect clamp on blur (5 effects)", all(clamp_ok), str(clamp_ok))
    record("all effect params exact up/down + clamp", not all_params["failures"],
           f"{all_params['count']} numeric params; failures={all_params['failures'][:4]}")
    record("step precision snapping", precision["a"] == 0.3 and precision["b"] == 1.1, json.dumps(precision))
    page.click('[data-section="effects"].section-reset')
    page.wait_for_timeout(300)

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

    # Round 1 Task 7: pointer + keyboard reorder, no accidental click drags.
    enable_effect("halftone")
    enable_effect("crt")
    enable_effect("pixelate")
    enable_effect("vignette")
    page.wait_for_timeout(350)
    order_js = "() => Array.from(document.querySelectorAll('#effects-list .effect-item')).map(e=>e.dataset.id).join(',')"
    before_order = page.evaluate(order_js)
    handle = page.locator('.effect-item[data-id="halftone"] .drag-handle')
    page.evaluate("""() => document.querySelector('.effect-item[data-id="halftone"] .drag-handle').scrollIntoView({block:'center'})""")
    page.wait_for_timeout(250)
    handle.hover()
    box = handle.bounding_box()
    second = page.locator('#effects-list .effect-item').nth(1).bounding_box()
    target_y = second["y"] + second["height"] * 0.7
    order_render_before = sig()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(330)
    lifted = page.locator(".reorder-ghost").count() == 1 and page.locator(".reorder-placeholder").count() == 1
    page.mouse.move(box["x"] + box["width"] / 2, target_y, steps=14)
    page.wait_for_timeout(260)
    page.mouse.up()
    page.wait_for_timeout(500)
    after_order = page.evaluate(order_js)
    record("effect pointer reorder", before_order != after_order and after_order.startswith("crt,halftone") and lifted,
           f"{before_order.split(',')[:3]} -> {after_order.split(',')[:3]}, lifted={lifted}")
    record("reorder cleans up ghost/placeholder", page.locator(".reorder-ghost").count() == 0 and page.locator(".reorder-placeholder").count() == 0)
    record("reorder changes output", sig() != order_render_before)

    page.locator("#effects-list .effect-item").first.locator(".drag-handle").focus()
    first_id = page.evaluate("() => document.activeElement.closest('.effect-item').dataset.id")
    page.keyboard.press("Alt+ArrowDown")
    page.wait_for_timeout(500)
    kbd_order = page.evaluate(order_js)
    focused_id = page.evaluate("() => document.activeElement.closest('.effect-item')?.dataset.id")
    record("effect keyboard reorder", kbd_order.split(",")[0] != first_id and kbd_order.split(",")[1] == first_id and focused_id == first_id,
           f"{first_id} moved, order {kbd_order.split(',')[:3]}, focus={focused_id}")

    touch_before = page.evaluate(order_js)
    page.evaluate("""() => {
      const items = Array.from(document.querySelectorAll('#effects-list .effect-item'));
      const handle = items[0].querySelector('.drag-handle');
      const h = handle.getBoundingClientRect();
      const t = items[1].getBoundingClientRect();
      const x = h.left + h.width / 2, y = h.top + h.height / 2, ty = t.top + t.height * 0.7;
      const base = {bubbles:true, cancelable:true, pointerId:99, pointerType:'touch', isPrimary:true, button:0, clientX:x, clientY:y};
      handle.dispatchEvent(new PointerEvent('pointerdown', base));
      window.dispatchEvent(new PointerEvent('pointermove', Object.assign({}, base, {clientY:ty, buttons:1})));
      window.dispatchEvent(new PointerEvent('pointerup', Object.assign({}, base, {clientY:ty, buttons:0})));
    }""")
    page.wait_for_timeout(600)
    touch_after = page.evaluate(order_js)
    record("effect touch-pointer reorder", touch_after != touch_before and touch_after.split(",")[1] == touch_before.split(",")[0],
           f"{touch_before.split(',')[:3]} -> {touch_after.split(',')[:3]}")

    click_before = page.evaluate(order_js)
    page.locator('#effects-list .effect-item[data-id="halftone"] .drag-handle').click()
    page.wait_for_timeout(250)
    record("plain handle click does not reorder", page.evaluate(order_js) == click_before)

    wheel_before = page.evaluate(order_js)
    page.locator('#effects-list .effect-item[data-id="halftone"] .drag-handle').hover()
    page.mouse.wheel(0, 320)
    page.wait_for_timeout(300)
    record("wheel scroll over handle does not reorder", page.evaluate(order_js) == wheel_before)

    state_order = page.evaluate("() => state.opts.effects.map(e => e.id).join(',')")
    record("render order equals stack order", page.evaluate(order_js) == state_order)
    order_before_edit = page.evaluate(order_js)
    set_effect_number("pixelate", 9)
    page.wait_for_timeout(500)
    record("reorder survives parameter edit", page.evaluate(order_js) == order_before_edit)

    page.evaluate("""() => document.querySelector('.effect-item[data-id="halftone"] .drag-handle').scrollIntoView({block:'center'})""")
    page.wait_for_timeout(250)
    panel_box = page.locator('.panel-content').bounding_box()
    scroll_before = page.evaluate("() => document.querySelector('.panel-content').scrollTop")
    auto_handle = page.locator('.effect-item[data-id="halftone"] .drag-handle')
    auto_handle.hover()
    auto_box = auto_handle.bounding_box()
    page.mouse.move(auto_box["x"] + auto_box["width"] / 2, auto_box["y"] + auto_box["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(330)
    page.mouse.move(auto_box["x"] + auto_box["width"] / 2, panel_box["y"] + panel_box["height"] - 18, steps=10)
    page.wait_for_timeout(900)
    scroll_after = page.evaluate("() => document.querySelector('.panel-content').scrollTop")
    page.mouse.up()
    page.wait_for_timeout(350)
    record("reorder edge auto-scroll", scroll_after > scroll_before + 10, f"{scroll_before} -> {scroll_after}")
    page.click('[data-section="effects"].section-reset')
    page.wait_for_timeout(300)

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

    # Round 2 Phase 4: View > Theme is present and switches the theme.
    page.keyboard.press("Escape")
    set_theme(True)
    open_menu("view")
    theme_item = page.locator('#dropdown-view [data-action="theme"]')
    theme_before = page.evaluate("() => document.documentElement.dataset.theme")
    theme_label = theme_item.inner_text() if theme_item.count() else ""
    theme_item.click()
    page.wait_for_timeout(300)
    theme_after = page.evaluate("() => document.documentElement.dataset.theme")
    record("theme item present in View menu",
           theme_item.count() == 1 and "Theme" in theme_label and theme_before == "dark" and theme_after == "light",
           f"count={theme_item.count()}, label={theme_label!r}, {theme_before} -> {theme_after}")
    set_theme(True)

    def menu_palette(dark):
        set_theme(dark)
        open_menu("view")
        data = page.evaluate("""() => {
          function parse(s){ const m=s.match(/rgba?\\(([^)]+)\\)/); return m ? m[1].split(/[ ,/]+/).filter(Boolean).map(Number) : null; }
          function lum(c){ const f=v=>{v/=255; return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);}; return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2]); }
          function ratio(a,b){ const l1=lum(a), l2=lum(b); return (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05); }
          const dd=document.getElementById('dropdown-view');
          const cs=getComputedStyle(dd);
          const item=dd.querySelector('.menu-item');
          const key=dd.querySelector('.menu-key');
          const bg=parse(cs.backgroundColor), fg=parse(getComputedStyle(item).color), muted=parse(getComputedStyle(key).color);
          return {bg:cs.backgroundColor, fg:getComputedStyle(item).color, muted:getComputedStyle(key).color,
                  bgLum:lum(bg), fgLum:lum(fg), text:+ratio(fg,bg).toFixed(2), mutedRatio:+ratio(muted,bg).toFixed(2)};
        }""")
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        return data

    dark_menu = menu_palette(True)
    light_menu = menu_palette(False)
    record("inverse menu dark page (light menu)", dark_menu["bgLum"] > 0.5 and dark_menu["fgLum"] < 0.2 and dark_menu["text"] >= 4.5 and dark_menu["mutedRatio"] >= 4.5, json.dumps(dark_menu))
    record("inverse menu light page (dark menu)", light_menu["bgLum"] < 0.2 and light_menu["fgLum"] > 0.7 and light_menu["text"] >= 4.5 and light_menu["mutedRatio"] >= 4.5, json.dumps(light_menu))

    set_theme(True)
    page.click("#zoom-level")
    page.wait_for_timeout(200)
    accent = page.evaluate("""() => {
      function parse(s){ const m=s.match(/rgba?\\(([^)]+)\\)/); return m ? m[1].split(/[ ,/]+/).filter(Boolean).map(Number) : null; }
      function lum(c){ const f=v=>{v/=255; return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);}; return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2]); }
      const menu=document.getElementById('zoom-menu');
      const checked=menu.querySelector('[aria-checked="true"]');
      const bg=parse(getComputedStyle(menu).backgroundColor);
      const fg=parse(getComputedStyle(checked).color);
      const l1=lum(fg), l2=lum(bg);
      return {ratio:+(((Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05)).toFixed(2)), color:getComputedStyle(checked).color};
    }""")
    page.keyboard.press("Escape")
    zoom_border = page.evaluate("""() => {
      const z=getComputedStyle(document.querySelector('.zoom-controls'));
      const pct=getComputedStyle(document.getElementById('zoom-level'));
      const out=getComputedStyle(document.getElementById('zoom-out'));
      return {group:z.borderTopColor, width:z.borderTopWidth, pct:pct.borderTopColor, sep:out.borderInlineEndColor};
    }""")
    set_theme(False)
    light_accent = page.evaluate("""() => {
      function parse(s){ const m=s.match(/rgba?\\(([^)]+)\\)/); return m ? m[1].split(/[ ,/]+/).filter(Boolean).map(Number) : null; }
      function lum(c){ const f=v=>{v/=255; return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);}; return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2]); }
      const menu=document.getElementById('dropdown-view');
      const bg=getComputedStyle(document.documentElement).getPropertyValue('--menu-bg').trim();
      const accent=getComputedStyle(document.documentElement).getPropertyValue('--menu-accent').trim();
      function hex(c){ c=c.replace('#',''); return [parseInt(c.slice(0,2),16),parseInt(c.slice(2,4),16),parseInt(c.slice(4,6),16)]; }
      const a=lum(hex(accent)), b=lum(hex(bg));
      return {ratio:+(((Math.max(a,b)+0.05)/(Math.min(a,b)+0.05)).toFixed(2)), accent, bg};
    }""")
    set_theme(True)
    record("menu accent contrast both themes", accent["ratio"] >= 4.5 and light_accent["ratio"] >= 4.5,
           f"dark={accent}, light={light_accent}")
    record("zoom group border matches % box", zoom_border["group"] == zoom_border["pct"] and zoom_border["width"] == "1px" and zoom_border["sep"] != "rgba(0, 0, 0, 0)",
           json.dumps(zoom_border))

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
        if (el.id === 'panel-toggle' || el.classList.contains('drag-handle') || el.classList.contains('preset-native')) return;
        const r = el.getBoundingClientRect();
        if (r.width < 44 || r.height < 44) {
          out.push({tag: el.tagName, id: el.id, cls: String(el.className), w: Math.round(r.width), h: Math.round(r.height)});
        }
      });
      return out;
    }""")
    record("touch targets >= 44px", len(small_targets) == 0, json.dumps(small_targets[:8]))

    # Round 1 Task 8: real phone list, swatches, collapsed view, keyboard picker.
    set_theme(True)
    page.locator("#output-preset-trigger").scroll_into_view_if_needed()
    page.wait_for_timeout(200)
    page.click("#output-preset-trigger")
    page.wait_for_timeout(300)
    phone_data = page.evaluate("""() => {
      const phones = SIZE_PRESETS.filter(p => p.group === 'Phone wallpaper');
      return {count: phones.length, first: phones.slice(0,3).map(p => p.id),
              labels: phones.map(p => p.label), unverified: phones.filter(p => p.unverified).map(p => p.id),
              dims: Object.fromEntries(phones.map(p => [p.id, [p.w, p.h]]))};
    }""")
    expected_dims = {
        "iphone-12": [1170,2532], "iphone-12-mini": [1080,2340], "iphone-14-pro-max": [1290,2796],
        "iphone-16-pro": [1206,2622], "iphone-17-pro-max": [1320,2868], "iphone-18": [1206,2622],
        "galaxy-s25-ultra": [1440,3120], "galaxy-s20": [1440,3200],
    }
    dims_ok = all(phone_data["dims"].get(k) == v for k, v in expected_dims.items())
    generic = [label for label in phone_data["labels"] if "FHD+" in label or "QHD+" in label or label.startswith("iPhone Pro ")]
    record("phone list is real models, newest first", phone_data["count"] == 47 and phone_data["first"] == ["iphone-18-pro-max","iphone-18-pro","iphone-18"] and not generic,
           f"count={phone_data['count']}, first={phone_data['first']}, generic={generic}")
    record("phone resolutions match brief", dims_ok, json.dumps({k: phone_data["dims"].get(k) for k in expected_dims}))
    record("unverified 18/S26 marked", set(phone_data["unverified"]) == {"iphone-18-pro-max","iphone-18-pro","iphone-18","galaxy-s26-ultra","galaxy-s26-plus","galaxy-s26"},
           str(phone_data["unverified"]))

    def visible_phones():
        return page.evaluate("""() => Array.from(document.querySelectorAll('.preset-group[aria-label="Phone wallpaper"] .preset-option'))
          .filter(o => !o.closest('[inert]') && o.getBoundingClientRect().height > 0).map(o => o.dataset.presetId)""")
    collapsed = visible_phones()
    extra_h0 = page.evaluate("() => document.querySelector('.preset-phone-extra').getBoundingClientRect().height")
    record("phone list default shows 3", collapsed == ["iphone-18-pro-max","iphone-18-pro","iphone-18"] and extra_h0 == 0,
           f"{collapsed}, extra={extra_h0}")
    page.locator("[data-preset-more]").scroll_into_view_if_needed()
    page.click("[data-preset-more]")
    page.wait_for_timeout(450)
    expanded = visible_phones()
    extra_h1 = page.evaluate("() => document.querySelector('.preset-phone-extra').getBoundingClientRect().height")
    record("View more expands smoothly", len(expanded) == 47 and extra_h1 > 100 and page.inner_text("[data-preset-more]") == "View less",
           f"{len(expanded)} visible, height={round(extra_h1)}")
    page.click("[data-preset-more]")
    page.wait_for_timeout(450)
    extra_h2 = page.evaluate("() => document.querySelector('.preset-phone-extra').getBoundingClientRect().height")
    record("View less collapses", extra_h2 == 0 and page.inner_text("[data-preset-more]") == "View more", f"height={extra_h2}")

    swatches = page.evaluate("""() => {
      function rect(id){ const o=document.querySelector('.preset-option[data-preset-id="'+id+'"]'); const r=o.querySelector('svg rect');
        return {w:+r.getAttribute('width'), h:+r.getAttribute('height'),
                left:o.querySelector('.preset-swatch').getBoundingClientRect().left,
                nameLeft:o.querySelector('.preset-option-label').getBoundingClientRect().left}; }
      return {phone:rect('iphone-12'), wide:rect('yt-thumb')};
    }""")
    phone_ratio = swatches["phone"]["w"] / swatches["phone"]["h"]
    wide_ratio = swatches["wide"]["w"] / swatches["wide"]["h"]
    record("true-aspect swatches left of names",
           abs(phone_ratio - 1170/2532) < 0.02 and abs(wide_ratio - 16/9) < 0.02 and
           swatches["phone"]["left"] < swatches["phone"]["nameLeft"],
           json.dumps(swatches))

    page.fill("#output-preset-search", "S26")
    page.wait_for_timeout(250)
    s26 = page.evaluate("() => Array.from(document.querySelectorAll('.preset-option')).map(o => o.dataset.presetId)")
    page.fill("#output-preset-search", "iPhone 17 Pro Max")
    page.wait_for_timeout(250)
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    page.wait_for_timeout(700)
    chosen = page.evaluate("() => ({id: state.opts.outputPreset, w: state.opts.outputWidth, h: state.opts.outputHeight, label: document.getElementById('output-preset-value').textContent})")
    record("picker search + keyboard selection", len(s26) == 3 and chosen["id"] == "iphone-17-pro-max" and chosen["w"] == 1320 and chosen["h"] == 2868,
           f"s26={len(s26)}, chosen={chosen}")
    page.select_option("#output-preset", "original")
    page.wait_for_timeout(350)

    page.click("#output-preset-trigger")
    page.wait_for_timeout(250)
    scrollable = page.evaluate("""() => {
      const l=getComputedStyle(document.getElementById('output-preset-list'));
      return {overflow:l.overflowY, max:l.maxHeight, scrollHeight:document.getElementById('output-preset-list').scrollHeight,
              clientHeight:document.getElementById('output-preset-list').clientHeight};
    }""")
    record("preset dropdown is scrollable", scrollable["overflow"] == "auto" and scrollable["scrollHeight"] > scrollable["clientHeight"],
           json.dumps(scrollable))
    page.emulate_media(reduced_motion="reduce")
    page.wait_for_timeout(150)
    reduced = page.evaluate("() => getComputedStyle(document.querySelector('.preset-phone-extra')).transitionDuration")
    page.emulate_media(reduced_motion="no-preference")
    record("picker reduced-motion support", reduced in ("1e-05s", "0.00001s", "0.01ms"), reduced)
    page.locator("[data-preset-more]").scroll_into_view_if_needed()
    page.click("[data-preset-more]")
    page.wait_for_timeout(450)
    page.screenshot(path=f"{SHOT}/picker_dark.png")
    page.keyboard.press("Escape")
    set_theme(False)
    page.click("#output-preset-trigger")
    page.wait_for_timeout(250)
    page.locator("[data-preset-more]").scroll_into_view_if_needed()
    page.click("[data-preset-more]")
    page.wait_for_timeout(450)
    page.screenshot(path=f"{SHOT}/picker_light.png")
    page.keyboard.press("Escape")
    set_theme(True)

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

    # 360px pass: picker + inverse menu must fit and stay scrollable.
    mctx = browser.new_context(viewport={"width": 360, "height": 740}, color_scheme="dark", locale="en-US")
    mpage = mctx.new_page()
    m_errors = []
    mpage.on("pageerror", lambda e: m_errors.append(str(e)))
    mpage.goto(URL, wait_until="load")
    mpage.wait_for_timeout(500)
    mpage.set_input_files("#file-input", TEST_IMG)
    mpage.wait_for_selector(".canvas-area.has-content", timeout=15000)
    mpage.wait_for_timeout(800)
    mpage.locator("#output-preset-trigger").scroll_into_view_if_needed()
    mpage.click("#output-preset-trigger")
    mpage.wait_for_timeout(300)
    mpage.locator("[data-preset-more]").scroll_into_view_if_needed()
    mpage.click("[data-preset-more]")
    mpage.wait_for_timeout(450)
    mobile = mpage.evaluate("""() => {
      const p=document.getElementById('output-preset-popup').getBoundingClientRect();
      const l=document.getElementById('output-preset-list');
      const m=document.getElementById('dropdown-file').getBoundingClientRect();
      return {left:p.left, right:p.right, width:p.width, listScroll:l.scrollHeight>l.clientHeight,
              overflowX:document.documentElement.scrollWidth-innerWidth, menuRight:m.right, menuLeft:m.left};
    }""")
    mpage.screenshot(path=f"{SHOT}/picker_360_dark.png")
    record("360px picker fits + scrolls", mobile["left"] >= 0 and mobile["right"] <= 360 and mobile["listScroll"] and mobile["overflowX"] <= 1,
           json.dumps(mobile))
    mpage.keyboard.press("Escape")
    mpage.click("#menu-file")
    mpage.wait_for_timeout(250)
    menu_box = mpage.evaluate("""() => { const m=document.getElementById('dropdown-file').getBoundingClientRect(); return {left:m.left,right:m.right,width:m.width}; }""")
    record("360px menu fits", menu_box["left"] >= 0 and menu_box["right"] <= 360, json.dumps(menu_box))

    # Sticky action bar at 360 with the panel open, in both themes.
    mpage.keyboard.press("Escape")
    mpage.click("#panel-toggle-btn")
    mpage.wait_for_timeout(300)
    mpage.evaluate("() => { document.querySelector('.panel-content').scrollTop = 1200; }")
    mpage.wait_for_timeout(300)

    def actionbar_360():
        return mpage.evaluate("""() => {
          const b=document.getElementById('panel-actionbar'), r=b.getBoundingClientRect();
          const p=document.getElementById('panel');
          const pr=p.getBoundingClientRect();
          const hit=document.elementFromPoint(r.x+6, r.y+r.height/2);
          return {open:p.classList.contains('open'), w:r.width, pw:pr.width,
                  bg:getComputedStyle(b).backgroundColor, z:getComputedStyle(b).zIndex,
                  hit:hit&&(hit.id||hit.className)};
        }""")

    small_dark = actionbar_360()
    mpage.screenshot(path=f"{SHOT}/actionbar_360_dark.png")
    mpage.click("#theme-toggle")
    mpage.wait_for_timeout(300)
    small_light = actionbar_360()
    mpage.screenshot(path=f"{SHOT}/actionbar_360_light.png")
    actionbar_ok = all(
        d["open"] and d["w"] >= d["pw"] - 2 and d["bg"].startswith("rgb(") and
        int(d["z"]) >= 10 and "actionbar" in str(d["hit"])
        for d in (small_dark, small_light)
    )
    record("360px action bar solid + full width both themes", actionbar_ok,
           json.dumps({"dark": small_dark, "light": small_light}))
    mctx.close()

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
