// Resizable "Show how it works" panel, VS Code terminal style.
// Drag the top edge up to grow the panel over the Console and editor.
// Drag down to shrink it. Double-click the edge to switch size.
(function () {
  const col = document.querySelector(".editor-col");
  const how = document.querySelector(".how");
  const body = document.getElementById("howBody");
  if (!col || !how || !body) return;

  const KEY = "formalang.howHeight.v1";
  const MIN = 72;     // header plus grip
  const TABS = 36;    // file tab strip stays visible; set to 0 to reach the very top
  const FIXED_ROWS = "36px 24px minmax(0, 1fr) 170px";

  let base = null;    // the panel's default height, from the CSS sizing
  let dragging = false;
  let startY = 0;
  let startH = 0;
  let curH = 0;

  const grip = document.createElement("div");
  grip.className = "how-grip";
  grip.title = "Drag to resize. Double-click to switch size.";
  how.prepend(grip);

  if (getComputedStyle(col).position === "static") {
    col.style.position = "relative";
  }

  function isCollapsed() {
    return body.classList.contains("hidden");
  }

  function maxH() {
    return Math.max(MIN, col.clientHeight - TABS);
  }

  function clamp(h) {
    return Math.max(MIN, Math.min(maxH(), Math.round(h)));
  }

  // The overlay needs an opaque background so the panel hides what is behind it.
  function solidBg() {
    let n = how;
    while (n && n !== document.documentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && bg !== "rgba(0, 0, 0, 0)" && bg !== "transparent") return bg;
      n = n.parentElement;
    }
    return "#0f1115";
  }

  function clearOverlay() {
    how.style.position = "";
    how.style.top = "";
    how.style.left = "";
    how.style.right = "";
    how.style.bottom = "";
    how.style.height = "";
    how.style.zIndex = "";
    how.style.background = "";
    how.style.boxShadow = "";
  }

  function reset() {
    col.style.gridTemplateRows = "";
    clearOverlay();
  }

  // Measure the default height with no inline sizing applied.
  function measureBase() {
    reset();
    base = how.getBoundingClientRect().height;
  }

  // Up to the default height: the panel takes its own grid row (editor shrinks).
  // Above the default: the panel floats over the Console and editor.
  function apply(h) {
    if (h <= base) {
      clearOverlay();
      col.style.gridTemplateRows = `${FIXED_ROWS} ${h}px`;
    } else {
      col.style.gridTemplateRows = `${FIXED_ROWS} ${base}px`;
      how.style.position = "absolute";
      how.style.left = "0";
      how.style.right = "0";
      how.style.bottom = "0";
      how.style.top = "auto";
      how.style.height = `${h}px`;
      how.style.zIndex = "30";
      how.style.background = solidBg();
      how.style.boxShadow = "0 -10px 28px rgba(0, 0, 0, 0.45)";
    }
    curH = h;
  }

  function load() {
    try {
      const v = parseFloat(localStorage.getItem(KEY));
      return Number.isFinite(v) ? v : null;
    } catch {
      return null;
    }
  }

  function save(h) {
    try {
      localStorage.setItem(KEY, String(Math.round(h)));
    } catch {
      /* storage unavailable: the size simply is not remembered */
    }
  }

  function sync() {
    if (isCollapsed()) {
      grip.style.display = "none";
      reset();
      return;
    }
    grip.style.display = "";
    measureBase();
    const saved = load();
    if (saved === null) return; // default size, already applied by reset()
    apply(clamp(saved));
  }

  function toggleSize() {
    const current = how.getBoundingClientRect().height;
    const full = maxH();
    const half = clamp(full / 2);
    const target = Math.abs(current - full) < 4 ? half : full;
    apply(target);
    save(target);
  }

  grip.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || isCollapsed()) return;
    e.preventDefault();
    dragging = true;
    startY = e.clientY;
    startH = how.getBoundingClientRect().height;
    grip.setPointerCapture(e.pointerId);
    grip.classList.add("dragging");
    document.body.style.userSelect = "none";
  });

  grip.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    apply(clamp(startH + (startY - e.clientY)));
  });

  function endDrag() {
    if (!dragging) return;
    dragging = false;
    grip.classList.remove("dragging");
    document.body.style.userSelect = "";
    save(curH);
  }

  grip.addEventListener("pointerup", endDrag);
  grip.addEventListener("pointercancel", endDrag);
  grip.addEventListener("dblclick", toggleSize);

  new MutationObserver(sync).observe(body, {
    attributes: true,
    attributeFilter: ["class"],
  });

  window.addEventListener("resize", () => {
    if (!dragging && !isCollapsed()) sync();
  });

  sync();
})();