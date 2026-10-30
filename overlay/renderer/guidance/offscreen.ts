// 9 · Hidden: off-screen. A pill sticks to the nearest edge and points toward the target.
import type { GuideMsg, Local } from "../../shared/messages";
import { Bag, Ctx, Mounted, el, esc } from "../dom";

const ARROWS = { right: "→", left: "←", down: "↓", up: "↑" } as const;

export function mountOffscreen(ctx: Ctx, g: GuideMsg, local: Local): Mounted {
  const bag = new Bag();
  const dir = g.extra.direction ?? "right";
  const [px, py] = local.edge_point ?? [ctx.W / 2, ctx.H / 2];
  const arrow = `<span class="arr">${ARROWS[dir]}</span>`;
  const text = `${esc(g.extra.label ?? "Target")} is off-screen`;
  const p = bag.add(el(ctx.ov, `edge ${dir}`, "", dir === "left" || dir === "up" ? `${arrow} ${text}` : `${text} ${arrow}`));
  const w = p.offsetWidth, h = p.offsetHeight;
  const x = Math.min(Math.max(8, dir === "right" ? px - w : dir === "left" ? px : px - w / 2), ctx.W - w - 8);
  const y = Math.min(Math.max(8, dir === "down" ? py - h : dir === "up" ? py : py - h / 2), ctx.H - h - 8);
  p.style.left = `${x}px`;
  p.style.top = `${y}px`;
  return { anchor: { x, y, w, h }, remove: () => bag.remove() };
}
