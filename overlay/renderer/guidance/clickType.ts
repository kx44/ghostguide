// 11 · Click type: for the first right / double / modifier click, a slim mouse next to the outline shows
// which button and how many times: that button lights up once per click (twice, quickly, for a double),
// and a modifier key-cap beside it presses in time. Used alone (style click_type = outline + mouse) or
// added to path chips.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, kc, outline, toRect } from "../dom";

// Slim outline mouse (guidance style 11): a line icon in one solid colour, no body fill, with a scroll wheel and
// the two buttons split by a thin line. 20 x 30 sits with Fluent's 20-24 px icons, and beside a toolbar button rather
// than over it. Drawn in a 20 x 30 grid, so the stroke widths in tokens.css are real pixels.
const MOUSE_W = 20, MOUSE_H = 30;
const MOUSE = (button: string, count: number) => {
  const press = `class="mbtn on p${Math.min(count, 2)}"`;
  return `<svg class="mouse" width="${MOUSE_W}" height="${MOUSE_H}" viewBox="0 0 ${MOUSE_W} ${MOUSE_H}" aria-hidden="true">
    <path ${button === "left" ? press : `class="mbtn"`} d="M10 1 V13 H1 V10 A9 9 0 0 1 10 1Z"/>
    <path ${button === "right" ? press : `class="mbtn"`} d="M10 1 V13 H19 V10 A9 9 0 0 0 10 1Z"/>
    <path d="M10 1 V13 M1 13 H19" class="msplit"/>
    <rect x="1" y="1" width="18" height="28" rx="9" class="mbody"/>
    <rect x="9" y="5" width="2" height="4" rx="1" class="mwheel"/></svg>`;
};

export function mountClickType(ctx: Ctx, g: GuideMsg, local: Local, withOutline = true): Mounted {
  const bag = new Bag();
  const r = toRect(local.box)!;
  const ct = g.extra.click_type ?? { button: "left", count: 1, modifiers: [], label: "Click" };
  const ol = withOutline ? bag.add(outline(ctx.ov, r)) : undefined;
  const mods = ct.modifiers.map(m => kc(m, "sm").replace('class="kc', `class="kc kpress p${Math.min(ct.count, 2)}`)).join(" ");
  const right = r.x + r.w + 16 + MOUSE_W + (mods ? 70 : 0) < ctx.W;
  const x = right ? r.x + r.w + 10 : r.x - 10 - MOUSE_W - (mods ? 62 : 0);
  bag.add(el(ctx.ov, "clicktype", `left:${x}px;top:${r.y + r.h / 2 - MOUSE_H / 2}px`,
    MOUSE(ct.button, ct.count) + (mods ? `<span class="mods">${mods}</span>` : "")));
  return {
    anchor: r,
    mark(result) { ol?.classList.remove("ok", "bad"); ol?.classList.add(result); },
    remove: () => bag.remove(),
  };
}
