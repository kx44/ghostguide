// 6 · Keyboard shortcut: big key-caps in the card; a dashed outline marks the button equivalent if pinned.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, kc, outline, toRect } from "../dom";

export function keycapsHtml(keys: string[]): string {
  return `<div class="keys">${keys.map(k => kc(k)).join('<span class="plus">+</span>')}</div>`;
}

export function mountKeycaps(ctx: Ctx, g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box);
  if (r) {
    bag.add(outline(ctx.ov, r, "dash"));
    const p = bag.add(el(ctx.ov, "pill", "", "same as this button"));
    p.style.left = `${r.x + r.w + 10}px`;
    p.style.top = `${r.y + r.h / 2 - 11}px`;
  }
  const keys = g.extra.keys ?? [];
  return {
    anchor: r,
    cardHtml: keys.length ? keycapsHtml(keys) : "",
    mark(result) {
      if (result !== "ok") return;
      document.querySelectorAll(".card .keys .kc").forEach(k => k.classList.add("done"));
    },
    remove: () => bag.remove(),
  };
}
