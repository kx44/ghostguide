// 5 · Type a value: outline the input and show the expected value as ghost text in it.
// Per-character matching needs the keyboard watcher (phase 3); phase 2 shows the value and the then-key.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, esc, kc, outline, toRect } from "../dom";

const MAX_LINES = 18;

export function mountGhostText(ctx: Ctx, g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box)!;
  const value = g.extra.value ?? "";
  const multi = !!g.extra.multiline;
  const ol = bag.add(outline(ctx.ov, r));
  let shown = value.replace(/\n$/, "");
  if (multi) {
    const lines = shown.split("\n");
    if (lines.length > MAX_LINES) shown = lines.slice(0, MAX_LINES).join("\n") + "\n…";
  }
  const t = bag.add(el(ctx.ov, multi ? "ghosttxt code" : "ghosttxt", "", esc(shown)));
  const size = multi ? 14 : Math.max(11, Math.min(16, Math.round(r.h * 0.62)));
  t.style.left = `${r.x + 6}px`;
  t.style.top = multi ? `${r.y + 1}px` : `${r.y + (r.h - size * 1.25) / 2}px`;
  t.style.fontSize = `${size}px`;
  if (!multi) { t.style.lineHeight = `${size * 1.25}px`; t.style.maxWidth = `${r.w - 10}px`; }
  else t.style.maxHeight = `${ctx.H - r.y - 20}px`;
  if (g.extra.then_key && !multi) {
    const h = bag.add(el(ctx.ov, "pill", "", `then ${kc(g.extra.then_key, "sm")}`));
    h.style.left = `${r.x + r.w + 10}px`;
    h.style.top = `${r.y + r.h / 2 - 11}px`;
  }
  // The code itself is already on screen as ghost text; the card repeats it only if it's long and clipped.
  const card = multi && value.split("\n").length > MAX_LINES ? `<pre class="code">${esc(value)}</pre>` : "";
  return {
    anchor: multi ? { x: r.x, y: r.y, w: r.w, h: r.h } : r,
    prefer: multi ? ["right", "left", "above", "below"] : undefined,
    cardHtml: card + (g.extra.then_key && multi ? `<div class="alt">Then press ${kc(g.extra.then_key, "sm")}</div>` : ""),
    mark(result) { ol.classList.remove("ok", "bad"); ol.classList.add(result); if (result === "ok") t.remove(); },
    remove: () => bag.remove(),
  };
}
