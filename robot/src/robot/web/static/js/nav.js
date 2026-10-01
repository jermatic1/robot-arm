// D-pad navigation: arrow keys move focus to the nearest visible control in that direction.

const DIRECTIONS = {
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
};

function focusables() {
  return [...document.querySelectorAll("button, input")].filter(
    (el) => !el.disabled && el.offsetParent !== null,
  );
}

function center(el) {
  const r = el.getBoundingClientRect();
  return [r.left + r.width / 2, r.top + r.height / 2];
}

function move(dx, dy) {
  const current = document.activeElement;
  const candidates = focusables();
  if (!candidates.includes(current)) {
    candidates[0]?.focus();
    return;
  }
  const [cx, cy] = center(current);
  let best = null;
  let bestScore = Infinity;
  for (const el of candidates) {
    if (el === current) continue;
    const [x, y] = center(el);
    const along = (x - cx) * dx + (y - cy) * dy;
    if (along <= 1) continue;
    const across = Math.abs((x - cx) * dy) + Math.abs((y - cy) * dx);
    const score = along + across * 2;
    if (score < bestScore) {
      best = el;
      bestScore = score;
    }
  }
  best?.focus();
  best?.scrollIntoView({ block: "nearest" });
}

export function focusFirst(root) {
  const el = [...root.querySelectorAll("button, input")].find((e) => !e.disabled);
  el?.focus();
}

export function ensureFocus() {
  if (!focusables().includes(document.activeElement)) focusables()[0]?.focus();
}

export function install(onBack) {
  document.addEventListener("keydown", (event) => {
    const dir = DIRECTIONS[event.key];
    const typing = document.activeElement?.tagName === "INPUT";
    if (dir) {
      // Left/right edit text inside an input; up/down always leave it.
      if (typing && dir[0] !== 0) return;
      event.preventDefault();
      move(...dir);
    } else if (event.key === "Escape" || (event.key === "Backspace" && !typing)) {
      event.preventDefault();
      onBack();
    }
  });
  // The TV app asks the page what Back should do; false means "leave the app".
  window.robotBack = onBack;
}
