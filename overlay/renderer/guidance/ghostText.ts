// 5 · Type a value: outline the input and show the expected value as ghost text in it.
// Shows the value and the then-key; there is no per-character matching.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, esc, kc, outline, toRect } from "../dom";

const MAX_LINES = 18;
const CHAR_PER_LINE_H = 0.405;   // editor character width / line height (see mountGhostText)

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
  const clip = local.clip;
  const t = bag.add(el(ctx.ov, (multi ? "ghosttxt code" : "ghosttxt") + (clip ? " backed" : ""), "", esc(shown)));
  if (clip && g.box) {
    // In an editor: on the editor's own lines and font size, on a solid backing in its background colour
    // (so the code already on those lines doesn't show through), cut off at the editor's edges.
    const lh = (g.extra.line_h ?? g.box.h - 4) * (r.h / g.box.h);
    // VS Code's default font (Consolas, monospaced): 0.55 em per character = 0.405 × its 19/14 line height.
    const left = r.x + 6 + (g.extra.col ?? 0) * lh * CHAR_PER_LINE_H, top = r.y + 2;
    t.style.left = `${left}px`;
    t.style.top = `${top}px`;
    t.style.fontSize = `${Math.round(lh * 0.74)}px`;
    t.style.lineHeight = `${lh}px`;
    if (g.extra.backing) t.style.background = g.extra.backing;
    t.style.maxWidth = `${Math.max(40, clip.x + clip.w - left)}px`;
    t.style.maxHeight = `${Math.max(lh, clip.y + clip.h - top)}px`;
  } else {
    const size = multi ? 14 : Math.max(11, Math.min(16, Math.round(r.h * 0.62)));
    t.style.left = `${r.x + 6}px`;
    t.style.top = multi ? `${r.y + 1}px` : `${r.y + (r.h - size * 1.25) / 2}px`;
    t.style.fontSize = `${size}px`;
    if (!multi) { t.style.lineHeight = `${size * 1.25}px`; t.style.maxWidth = `${r.w - 10}px`; }
    else t.style.maxHeight = `${ctx.H - r.y - 20}px`;
  }
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
