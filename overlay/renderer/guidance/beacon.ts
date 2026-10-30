// 3 · Button, repeat: a pulsing dot on the target's top-right corner. No outline, no card.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, outline, toRect } from "../dom";

export function mountBeacon(ctx: Ctx, _g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box)!;
  bag.add(el(ctx.ov, "beacon", `left:${r.x + r.w - 6}px;top:${r.y - 6}px`));
  return {
    anchor: r,
    mark(result) { bag.remove(); bag.add(outline(ctx.ov, r, result)); },
    remove: () => bag.remove(),
  };
}
