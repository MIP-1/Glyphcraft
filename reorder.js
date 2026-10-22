// Reusable pointer + keyboard reorder list.
// Used by the effect stack; the same module can drive drag-to-add later.
(function (global) {
  "use strict";

  function createReorderList(options) {
    var container = options.container;
    if (!container) return null;

    var itemSelector = options.itemSelector || ".effect-item";
    var handleSelector = options.handleSelector || ".drag-handle";
    var longPress = options.longPress || 250;
    var moveThreshold = options.moveThreshold || 4;
    var edge = options.edge || 56;
    var onReorder = options.onReorder || function () {};
    var scroller = options.scrollContainer || container.closest(".panel-content") || document.scrollingElement;

    var pending = null;
    var drag = null;
    var pressTimer = 0;
    var scrollFrame = 0;

    function items() {
      return Array.prototype.slice.call(container.querySelectorAll(itemSelector));
    }
    function indexOf(el) {
      return items().indexOf(el);
    }
    function clearPressTimer() {
      if (pressTimer) { clearTimeout(pressTimer); pressTimer = 0; }
    }
    function removeWindowListeners() {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerCancel);
      window.removeEventListener("keydown", onEscape);
      clearPressTimer();
    }

    function onPointerDown(e) {
      if (pending || drag) return;
      if (e.button !== undefined && e.button !== 0) return;
      var handle = e.target.closest(handleSelector);
      if (!handle || !container.contains(handle)) return;
      var item = handle.closest(itemSelector);
      if (!item || item.classList.contains("reorder-source")) return;

      // Only the handle starts a reorder, so scrolling the panel is safe.
      e.preventDefault();
      handle.focus({ preventScroll: true });
      pending = {
        pointerId: e.pointerId,
        handle: handle,
        item: item,
        from: indexOf(item),
        startX: e.clientX,
        startY: e.clientY
      };
      pressTimer = setTimeout(function () {
        if (pending && pending.item.isConnected) activate(pending.startX, pending.startY, pending.startY);
      }, longPress);
      window.addEventListener("pointermove", onPointerMove, { passive: false });
      window.addEventListener("pointerup", onPointerUp);
      window.addEventListener("pointercancel", onPointerCancel);
      window.addEventListener("keydown", onEscape);
    }

    function onPointerMove(e) {
      if (!pending) return;
      if (e.pointerId !== undefined && e.pointerId !== pending.pointerId) return;
      if (!drag) {
        var dx = e.clientX - pending.startX;
        var dy = e.clientY - pending.startY;
        if (Math.hypot(dx, dy) < moveThreshold) return;
        clearPressTimer();
        activate(e.clientX, e.clientY, e.clientY);
        return;
      }
      e.preventDefault();
      updateDrag(e.clientX, e.clientY);
    }

    function onPointerUp(e) {
      if (pending && e.pointerId !== undefined && e.pointerId !== pending.pointerId) return;
      if (drag) finishDrag();
      else {
        pending = null;
        removeWindowListeners();
      }
    }

    function onPointerCancel(e) {
      if (pending && e.pointerId !== undefined && e.pointerId !== pending.pointerId) return;
      if (drag) cancelDrag();
      pending = null;
      removeWindowListeners();
    }

    function onEscape(e) {
      if (e.key !== "Escape" || !drag) return;
      e.preventDefault();
      cancelDrag();
      pending = null;
      removeWindowListeners();
    }

    function activate(x, y, pointerY) {
      if (!pending || drag) return;
      if (!pending.item.isConnected || !pending.item.parentNode) {
        pending = null;
        removeWindowListeners();
        return;
      }
      var item = pending.item;
      var rect = item.getBoundingClientRect();
      // Freeze the slot centres at activation. Re-measuring live would let the
      // list shift under the pointer and cascade past the intended slot.
      var scrollerTop = scroller.getBoundingClientRect().top;
      var slots = items().filter(function (el) { return el !== item; }).map(function (el) {
        var r = el.getBoundingClientRect();
        return { el: el, center: r.top - scrollerTop + scroller.scrollTop + r.height / 2 };
      });
      var ghost = item.cloneNode(true);
      ghost.classList.remove("reorder-source");
      ghost.classList.add("reorder-ghost");
      ghost.removeAttribute("data-reorder-focus");
      ghost.style.width = rect.width + "px";
      ghost.style.height = rect.height + "px";
      ghost.style.left = rect.left + "px";
      ghost.style.top = rect.top + "px";
      document.body.appendChild(ghost);

      var placeholder = document.createElement("div");
      placeholder.className = "reorder-placeholder";
      placeholder.style.height = rect.height + "px";
      item.parentNode.insertBefore(placeholder, item);
      item.classList.add("reorder-source");

      drag = {
        item: item,
        ghost: ghost,
        placeholder: placeholder,
        from: pending.from,
        slots: slots,
        offsetX: Math.max(0, Math.min(rect.width, x - rect.left)),
        offsetY: Math.max(0, Math.min(rect.height, y - rect.top)),
        lastX: x,
        lastY: pointerY == null ? y : pointerY
      };
      document.body.classList.add("reorder-active");
      updateDrag(x, pointerY == null ? y : pointerY);
      startAutoScroll();
    }

    function updateDrag(x, y) {
      if (!drag) return;
      drag.lastX = x;
      drag.lastY = y;
      drag.ghost.style.left = (x - drag.offsetX) + "px";
      drag.ghost.style.top = (y - drag.offsetY) + "px";

      var scrollerRect = scroller.getBoundingClientRect();
      var contentY = y - scrollerRect.top + scroller.scrollTop;
      var before = null;
      for (var i = 0; i < drag.slots.length; i++) {
        if (contentY < drag.slots[i].center) { before = drag.slots[i].el; break; }
      }
      movePlaceholder(before);
    }

    // FLIP: measure, move the placeholder, then animate neighbours from their
    // old position to the new one so the stack slides instead of jumping.
    function movePlaceholder(before) {
      if (!drag || !drag.placeholder || !drag.placeholder.isConnected) return;
      var ph = drag.placeholder;
      var movers = items().filter(function (el) { return el !== drag.item; });
      var first = new Map();
      movers.forEach(function (el) { first.set(el, el.getBoundingClientRect().top); });

      if (before) container.insertBefore(ph, before);
      else container.appendChild(ph);

      movers.forEach(function (el) {
        var delta = first.get(el) - el.getBoundingClientRect().top;
        if (!delta) return;
        el.style.transition = "none";
        el.style.transform = "translateY(" + delta + "px)";
        requestAnimationFrame(function () {
          el.style.transition = "transform 0.16s ease";
          el.style.transform = "";
          setTimeout(function () {
            el.style.transition = "";
            el.style.transform = "";
          }, 180);
        });
      });
    }

    function targetIndex() {
      var all = items();
      var to = 0;
      for (var i = 0; i < all.length; i++) {
        if (all[i] === drag.item) continue;
        if (all[i].compareDocumentPosition(drag.placeholder) & Node.DOCUMENT_POSITION_FOLLOWING) to++;
      }
      return to;
    }

    function finishDrag() {
      var from = drag.from;
      var to = targetIndex();
      cleanupDrag();
      pending = null;
      removeWindowListeners();
      if (to !== from && from >= 0) onReorder(from, to);
    }

    function cancelDrag() {
      cleanupDrag();
    }

    function cleanupDrag() {
      if (!drag) return;
      stopAutoScroll();
      if (drag.ghost && drag.ghost.parentNode) drag.ghost.parentNode.removeChild(drag.ghost);
      if (drag.placeholder && drag.placeholder.parentNode) drag.placeholder.parentNode.removeChild(drag.placeholder);
      drag.item.classList.remove("reorder-source");
      drag.item.style.transform = "";
      document.body.classList.remove("reorder-active");
      items().forEach(function (el) { el.style.transform = ""; el.style.transition = ""; });
      drag = null;
    }

    function scrollSpeed(y) {
      if (!scroller) return 0;
      var r = scroller.getBoundingClientRect();
      if (r.height <= edge * 2) return 0;
      if (y < r.top + edge) return -Math.min(14, Math.ceil((r.top + edge - y) / 3));
      if (y > r.bottom - edge) return Math.min(14, Math.ceil((y - (r.bottom - edge)) / 3));
      return 0;
    }

    function startAutoScroll() {
      stopAutoScroll();
      function tick() {
        if (!drag) return;
        var delta = scrollSpeed(drag.lastY);
        if (delta) {
          var before = scroller.scrollTop;
          scroller.scrollTop = before + delta;
          if (scroller.scrollTop !== before) updateDrag(drag.lastX, drag.lastY);
        }
        scrollFrame = requestAnimationFrame(tick);
      }
      scrollFrame = requestAnimationFrame(tick);
    }

    function stopAutoScroll() {
      if (scrollFrame) { cancelAnimationFrame(scrollFrame); scrollFrame = 0; }
    }

    function onKeyDown(e) {
      if (drag || !e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
      var handle = e.target.closest(handleSelector);
      if (!handle || !container.contains(handle)) return;
      var item = handle.closest(itemSelector);
      if (!item) return;
      var list = items();
      var from = list.indexOf(item);
      var to = from + (e.key === "ArrowUp" ? -1 : 1);
      if (from < 0 || to < 0 || to >= list.length) return;
      e.preventDefault();
      onReorder(from, to);
    }

    container.addEventListener("pointerdown", onPointerDown);
    container.addEventListener("keydown", onKeyDown);

    return {
      destroy: function () {
        container.removeEventListener("pointerdown", onPointerDown);
        container.removeEventListener("keydown", onKeyDown);
        removeWindowListeners();
        cancelDrag();
      }
    };
  }

  global.createReorderList = createReorderList;
})(window);
