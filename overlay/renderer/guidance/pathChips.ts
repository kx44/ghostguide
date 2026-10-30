// 8 · Hidden: menu path. The card shows the route as chips; done hops are ticked; the outline sits on the
// current hop (phase 2: the pinned box; hop-by-hop tracking needs UIA, phase 3/4).
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, esc, outline, toRect } from "../dom";
import { mountClickType } from "./clickType";

export function chipsHtml(path: string[], done: number): string {
  return `<div class="chips">${path.map((t, i) =>
    `<span class="chip ${i < done ? "done" : i === done ? "cur" : ""}">${i < done ? "✓ " : ""}${esc(t)}</span>${i < path.length - 1 ? "›" : ""}`).join("")}</div>`;
}

export function mountPathChips(ctx: Ctx, g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box);
  const ol = r ? bag.add(outline(ctx.ov, r)) : undefined;
  const mouse = r && g.extra.click_type ? mountClickType(ctx, g, local, false) : undefined;
  if (mouse) bag.onRemove(() => mouse.remove());
  return {
    anchor: r,
    wide: true,
    cardTop: chipsHtml(g.extra.path ?? [], g.extra.path_done ?? 0),
    cardHtml: g.extra.shortcut ? `<div class="alt">Shortcut: ${esc(g.extra.shortcut)}</div>` : "",
    mark(result) { ol?.classList.remove("ok", "bad"); ol?.classList.add(result); },
    remove: () => bag.remove(),
  };
}
