// 11 · Click type: for the first right / double / modifier click, a slim mouse next to the outline shows
// which button and how many times: that button lights up once per click (twice, quickly, for a double),
// and a modifier key-cap beside it presses in time. Used alone (style click_type = outline + mouse) or
// added to path chips.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, kc, outline, toRect } from "../dom";

// Slim outline mouse (glossary style 11, chosen 30 Oct): 30×44, violet line, dark/light body per scheme,
// thin halo underneath so it reads on any background, scroll wheel, the two buttons split by a faint line.
const MOUSE = (button: string, count: number) => {
  const press = `class="mbtn on p${Math.min(count, 2)}"`;
  return `<svg class="mouse" width="30" height="44" viewBox="0 0 30 44" aria-hidden="true">
    <rect x="2" y="2" width="26" height="40" rx="13" class="mhalo"/>
    <rect x="2" y="2" width="26" height="40" rx="13" class="mbody"/>
    <path ${button === "left" ? press : `class="mbtn"`} d="M15 3.5 V19 H3.5 V15 A11.5 11.5 0 0 1 15 3.5Z"/>
    <path ${button === "right" ? press : `class="mbtn"`} d="M15 3.5 V19 H26.5 V15 A11.5 11.5 0 0 0 15 3.5Z"/>
    <path d="M15 3 V19 M3 19 H27" class="msplit"/>
    <rect x="13.5" y="8" width="3" height="6" rx="1.5" class="mwheel"/></svg>`;
};

export function mountClickType(ctx: Ctx, g: GuideMsg, local: Local, withOutline = true): Mounted {
  const bag = new Bag();
  const r = toRect(local.box)!;
  const ct = g.extra.click_type ?? { button: "left", count: 1, modifiers: [], label: "Click" };
  const ol = withOutline ? bag.add(outline(ctx.ov, r)) : undefined;
  const mods = ct.modifiers.map(m => kc(m, "sm").replace('class="kc', `class="kc kpress p${Math.min(ct.count, 2)}`)).join(" ");
  const right = r.x + r.w + 16 + 30 + (mods ? 70 : 0) < ctx.W;
  const x = right ? r.x + r.w + 12 : r.x - 12 - 30 - (mods ? 62 : 0);
  bag.add(el(ctx.ov, "clicktype", `left:${x}px;top:${r.y + r.h / 2 - 22}px`,
    MOUSE(ct.button, ct.count) + (mods ? `<span class="mods">${mods}</span>` : "")));
  return {
    anchor: r,
    mark(result) { ol?.classList.remove("ok", "bad"); ol?.classList.add(result); },
    remove: () => bag.remove(),
  };
}
