// 1 · Button, first time: outline + tooltip (the card is mounted by app.ts).
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, outline, toRect } from "../dom";

export function mountOutline(ctx: Ctx, _g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box);
  const ol = r ? bag.add(outline(ctx.ov, r)) : undefined;
  return {
    anchor: r,
    mark(result) { ol?.classList.remove("ok", "bad"); ol?.classList.add(result); },
    remove: () => bag.remove(),
  };
}
