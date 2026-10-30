// 10 · Switch app: outline the target app's taskbar icon, with Alt + Tab as the keyboard route.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, kc, outline, toRect } from "../dom";

export function mountTaskbar(ctx: Ctx, _g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box)!;
  const ol = bag.add(outline(ctx.ov, r));
  return {
    anchor: r,
    prefer: ["above", "right", "left", "below"],
    cardHtml: `<div class="alt">Or press ${kc("Alt", "sm")} + ${kc("Tab", "sm")}</div>`,
    mark(result) { ol.classList.remove("ok", "bad"); ol.classList.add(result); },
    remove: () => bag.remove(),
  };
}
