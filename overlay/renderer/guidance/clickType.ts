// 11 · Click type: for the first right / double / modifier click, a small mouse next to the outline shows
// which button and how many times (+ a key-cap for the modifier). Used alone (style click_type = outline +
// mouse) or added to path chips.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, kc, outline, toRect } from "../dom";

export function mountClickType(ctx: Ctx, g: GuideMsg, local: Local, withOutline = true): Mounted {
  const bag = new Bag();
  const r = toRect(local.box)!;
  const ct = g.extra.click_type ?? { button: "left", count: 1, modifiers: [], label: "Click" };
  const ol = withOutline ? bag.add(outline(ctx.ov, r)) : undefined;
  const side = r.x + r.w + 60 < ctx.W ? r.x + r.w + 12 : r.x - 46;
  const mouse = bag.add(el(ctx.ov, "abs", `left:${side}px;top:${r.y + r.h / 2 - 24}px;animation:fade .3s`,
    `<svg width="34" height="49" viewBox="0 0 28 40" style="overflow:visible">
      <rect x="1.5" y="1.5" width="25" height="37" rx="12.5" style="fill:var(--mouse-bg);stroke:var(--halo)" stroke-width="5"/>
      <rect x="1.5" y="1.5" width="25" height="37" rx="12.5" style="fill:var(--mouse-bg);stroke:var(--g)" stroke-width="2.5"/>
      <path data-b="left" d="M14 2.5 V16 H2.5 V14 A11.5 11.5 0 0 1 14 2.5Z" style="fill:transparent"/>
      <path data-b="right" d="M14 2.5 V16 H25.5 V14 A11.5 11.5 0 0 0 14 2.5Z" style="fill:transparent"/>
      <path d="M14 2.5 V16 M2.5 16 H25.5" style="stroke:var(--g)" stroke-width="2"/></svg>` +
    (ct.count > 1 ? `<span class="pill" style="left:30px;top:-8px">×${ct.count}</span>` : "") +
    (ct.modifiers.length ? `<span style="position:absolute;left:38px;top:14px;white-space:nowrap">${ct.modifiers.map(m => kc(m, "sm")).join(" ")}</span>` : "")));
  const part = mouse.querySelector<SVGPathElement>(`[data-b="${ct.button}"]`)!;
  let alive = true;
  (async () => {
    const wait = (ms: number) => new Promise(res => setTimeout(res, ms));
    while (alive) {
      for (let i = 0; i < ct.count && alive; i++) {
        part.style.fill = "var(--g)"; await wait(ct.count > 1 ? 220 : 420);
        part.style.fill = "transparent"; await wait(ct.count > 1 ? 160 : 200);
      }
      await wait(700);
    }
  })();
  bag.onRemove(() => { alive = false; });
  return {
    anchor: r,
    mark(result) { ol?.classList.remove("ok", "bad"); ol?.classList.add(result); },
    remove: () => bag.remove(),
  };
}
