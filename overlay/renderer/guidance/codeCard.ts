// 5 · Type a value: mark where it goes and carry the text in the card's code box, with Copy. Nothing is
// drawn over the app's own text (inline ghost text was, and got messy over existing code).
//   insert "line"   the target line is empty (or past the end): outline it, type there
//   insert "before" it already has code: the new lines go between it and the line above, so a bar marks
//                   that gap instead of boxing a line that stays (boxing </article> read as "change this")
//   insert "col"    inside a line: outline the line + a thin caret at the column
//   insert "end"    appending to the file: a bar right under the last code, tagged "end of file"
//                   ("↓ Ctrl+End" when the end is scrolled out of view)
// The code box shows the code around the spot in purple (the line before, or the text either side of a
// mid-line insert) so the user sees where it goes; Copy copies only the new text.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, esc, kc, outline, toRect } from "../dom";

const CHAR_PER_LINE_H = 0.405;   // VS Code's Consolas: character width / line height (0.55 em at 19/14)

/** The code box: label, Copy, the text (with its purple context). Shared with the card-only fallback. */
export function codeBoxHtml(value: string, label = "Code", before?: string, after?: string, inline = false): string {
  const shown = value.replace(/\n$/, "");
  const ctx = (s?: string) => (s ? `<span class="ctx">${esc(s)}</span>` : "");
  const body = inline ? ctx(before) + esc(shown) + ctx(after) : (before ? ctx(before) + "\n" : "") + esc(shown);
  return `<div class="codebox"><div class="codehd"><span>${esc(label)}</span>` +
    `<button class="copy" data-copy="${esc(shown)}" title="Copy to the clipboard">Copy</button></div>` +
    `<pre>${body}</pre></div>`;
}

export function mountCodeCard(ctx: Ctx, g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box);
  const x = g.extra;
  const value = x.value ?? "";
  const multi = !!x.multiline || value.length > 40;
  let mark: HTMLElement | undefined;
  if (r && (x.insert === "before" || x.insert === "end" || x.scroll)) {
    mark = bag.add(el(ctx.ov, "insbar", ""));
    mark.style.left = `${r.x}px`;
    mark.style.top = `${r.y + 1}px`;
    mark.style.width = `${r.w}px`;
    const tag = x.scroll ? `${x.scroll === "down" ? "↓" : "↑"} ${x.insert === "end" ? "Ctrl+End" : "scroll"}`
      : x.insert === "end" ? "end of file" : "";
    if (tag) {
      const t = bag.add(el(ctx.ov, "instag", "", esc(tag)));
      t.style.left = `${r.x + r.w}px`;           // right end of the bar, just under it: clear of the code above
      t.style.transform = "translateX(-100%)";
      t.style.top = `${r.y + 7}px`;
    }
  } else if (r) {
    mark = bag.add(outline(ctx.ov, r));
  }
  if (r && g.box && x.col != null) {
    const lh = (x.line_h ?? g.box.h - 4) * (r.h / g.box.h);
    const caret = bag.add(el(ctx.ov, "inscaret", ""));
    caret.style.left = `${r.x + 6 + x.col * lh * CHAR_PER_LINE_H - 1}px`;
    caret.style.top = `${r.y + 3}px`;
    caret.style.height = `${r.h - 6}px`;
  }
  const label = x.label && x.label !== "Editor" ? x.label : multi ? "Code" : "Text";
  const then = x.then_key ? `<div class="alt">Then press ${kc(x.then_key, "sm")}</div>` : "";
  return {
    anchor: r,
    // Code goes on the marked line and the ones after it: keep the card beside them, not over them.
    prefer: multi ? ["right", "left", "below", "above"] : undefined,
    wide: multi,
    cardHtml: codeBoxHtml(value, label, x.context_before, x.context_after, x.insert === "col") + then,
    mark(result) { if (mark) { mark.classList.remove("ok", "bad"); mark.classList.add(result); } },
    remove: () => bag.remove(),
  };
}
