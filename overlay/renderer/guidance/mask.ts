// 7 · Pick in the model: tinted, breathing mask over the face or edge, with a plain-words label.
// An ellipse over the box, not the edge's real shape.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, esc, sv, toRect } from "../dom";

export function mountMask(ctx: Ctx, g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const r = toRect(local.box)!;
  const cx = r.x + r.w / 2, cy = r.y + r.h / 2, rx = r.w / 2, ry = r.h / 2;
  const mg = bag.add(sv(ctx.svg, "g", { class: "mask" }));
  const fill = sv(mg, "ellipse", { cx, cy, rx, ry, fill: "var(--gfill)" });
  const edge = sv(mg, "ellipse", { cx, cy, rx, ry, fill: "none", stroke: "var(--g)", "stroke-width": 2 });
  const lab = bag.add(el(ctx.ov, "pill", "", esc(g.extra.label ?? "")));
  lab.style.left = `${cx - lab.offsetWidth / 2}px`;
  lab.style.top = `${r.y + r.h + 8}px`;
  const lw = lab.offsetWidth, lx = cx - lw / 2;
  const x0 = Math.min(r.x, lx), x1 = Math.max(r.x + r.w, lx + lw);
  return {
    anchor: { x: x0, y: r.y, w: x1 - x0, h: r.h + 8 + lab.offsetHeight },   // keep the label clear of the card
    prefer: ["right", "left", "above", "below"],
    mark(result) {
      mg.classList.remove("mask");
      fill.remove();
      edge.style.stroke = result === "ok" ? "var(--ok)" : "var(--warn)";
    },
    remove: () => bag.remove(),
  };
}
