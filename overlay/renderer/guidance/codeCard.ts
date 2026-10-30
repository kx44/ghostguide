// 5 · Type a value: outline where it goes (the input, or the editor line), and the card carries the text in
// a code box with Copy. Nothing is drawn over the app's own text (inline ghost text was, and got messy over
// existing code). A mid-line insert also gets a thin caret at its column.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, esc, kc, outline, toRect } from "../dom";

const CHAR_PER_LINE_H = 0.405;   // VS Code's Consolas: character width / line height (0.55 em at 19/14)

/** The code box: label, Copy, the text. Shared with the card-only fallback (target not on screen). */
export function codeBoxHtml(value: string, label = "Code"): string {
  const shown = value.replace(/\n$/, "");
  return `<div class="codebox"><div class="codehd"><span>${esc(label)}</span>` +
    `<button class="copy" data-copy="${esc(shown)}" title="Copy to the clipboard">Copy</button></div>` +
    `<pre>${esc(shown)}</pre></div>`;
}

export function mountCodeCard(ctx: Ctx, g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box);
  const value = g.extra.value ?? "";
  const multi = !!g.extra.multiline || value.length > 40;
  const ol = r ? bag.add(outline(ctx.ov, r)) : undefined;
  if (r && g.box && g.extra.col != null) {
    const lh = (g.extra.line_h ?? g.box.h - 4) * (r.h / g.box.h);
    const caret = bag.add(el(ctx.ov, "inscaret", ""));
    caret.style.left = `${r.x + 6 + g.extra.col * lh * CHAR_PER_LINE_H - 1}px`;
    caret.style.top = `${r.y + 3}px`;
    caret.style.height = `${r.h - 6}px`;
  }
  const label = g.extra.label && g.extra.label !== "Editor" ? g.extra.label : multi ? "Code" : "Text";
  const then = g.extra.then_key ? `<div class="alt">Then press ${kc(g.extra.then_key, "sm")}</div>` : "";
  return {
    anchor: r,
    // Code goes on the line the outline marks and the lines after it: keep the card beside them, not over them.
    prefer: multi ? ["right", "left", "below", "above"] : undefined,
    wide: multi,
    cardHtml: codeBoxHtml(value, label) + then,
    mark(result) { if (ol) { ol.classList.remove("ok", "bad"); ol.classList.add(result); } },
    remove: () => bag.remove(),
  };
}
