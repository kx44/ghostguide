// 2 · Cursor action, first time: animated ghost line (+ card). 4 · Repeat: the same path, static, no card.
import type { GuideMsg, Local, Pt } from "../../shared/messages";
import { Bag, Ctx, Mounted, Rect, el, esc, halo, sv } from "../dom";

const LOOP_MS = 2400;

function path(ctx: Ctx, bag: Bag, o: Pt, e: Pt, pill?: string) {
  const g = bag.add(sv(ctx.svg, "g", {}));
  halo(g, "line", { x1: o[0], y1: o[1], x2: e[0], y2: e[1], stroke: "var(--g)", "stroke-dasharray": "8 6", "stroke-linecap": "round" }, 3);
  halo(g, "circle", { cx: o[0], cy: o[1], r: 7, stroke: "var(--g)", fill: "none" }, 2.5);
  sv(g, "circle", { cx: e[0], cy: e[1], r: 6.5, fill: "var(--halo)" });
  sv(g, "circle", { cx: e[0], cy: e[1], r: 5, fill: "var(--g)" });
  if (pill) {
    const p = bag.add(el(ctx.ov, "pill", "", esc(pill)));
    p.style.left = `${(o[0] + e[0]) / 2 - p.offsetWidth / 2}px`;
    p.style.top = `${Math.min(o[1], e[1]) - 32}px`;
  }
  return g;
}

function bounds(o: Pt, e: Pt): Rect {
  return { x: Math.min(o[0], e[0]), y: Math.min(o[1], e[1]), w: Math.max(1, Math.abs(e[0] - o[0])), h: Math.max(1, Math.abs(e[1] - o[1])) };
}

export function mountGhostLine(ctx: Ctx, g: GuideMsg, local: Local, animated = true): Mounted {
  const bag = new Bag();
  const o = local.line!.from, e = local.line!.to;
  const group = path(ctx, bag, o, e, g.extra.pill);
  let raf = 0;
  if (animated) {
    const grow = bag.add(sv(ctx.svg, "line", { x1: o[0], y1: o[1], x2: o[0], y2: o[1], stroke: "var(--g)", "stroke-width": 4, "stroke-linecap": "round" }));
    const ring = bag.add(sv(ctx.svg, "circle", { cx: o[0], cy: o[1], r: 0, fill: "none", stroke: "var(--g)", "stroke-width": 2.5 }));
    const t0 = performance.now();
    const ease = (u: number) => (u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2);
    const frame = (now: number) => {
      const u = (Math.max(0, now - t0) % LOOP_MS) / LOOP_MS;   // rAF time can be a hair before t0
      let len = 0, rr = 0, at: Pt = o;
      if (u < 0.12) rr = (u / 0.12) * 14;                                    // press pulse
      else if (u < 0.65) len = ease((u - 0.12) / 0.53);                       // grow
      else if (u < 0.78) { len = 1; rr = ((u - 0.65) / 0.13) * 14; at = e; }  // release pulse
      else len = 1;
      grow.setAttribute("x2", String(o[0] + (e[0] - o[0]) * len));
      grow.setAttribute("y2", String(o[1] + (e[1] - o[1]) * len));
      grow.setAttribute("opacity", String(u > 0.85 ? 1 - (u - 0.85) / 0.15 : 1));
      ring.setAttribute("cx", String(at[0])); ring.setAttribute("cy", String(at[1]));
      ring.setAttribute("r", String(rr)); ring.setAttribute("opacity", String(rr ? 1 - rr / 16 : 0));
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    bag.onRemove(() => cancelAnimationFrame(raf));
  }
  return {
    anchor: bounds(o, e),
    prefer: ["right", "left", "below", "above"],     // the card sits to the side, off the path
    mark(result) {
      cancelAnimationFrame(raf);
      group.querySelectorAll("line").forEach((l, i) => { if (i % 2) l.style.stroke = result === "ok" ? "var(--ok)" : "var(--warn)"; });
    },
    remove: () => bag.remove(),
  };
}
