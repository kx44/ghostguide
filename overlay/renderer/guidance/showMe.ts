// Show me: the violet ghost cursor moves to the target and plays the click (or the drag path). It never clicks.
import type { Pt } from "../../shared/messages";
import { NS, sleep } from "../dom";

const MOVE_MS = 900;
let token = 0;

export function ghostCursor(layer: HTMLElement): SVGSVGElement {
  const c = document.createElementNS(NS, "svg");
  c.id = "gcur";
  c.setAttribute("width", "40"); c.setAttribute("height", "40"); c.setAttribute("viewBox", "0 0 40 40");
  c.innerHTML = `<path d="M2 2 L2 24 L8 18 L12 27 L16 25 L12 17 L20 17 Z" style="fill:var(--g)"/>` +
    `<circle class="ring" cx="2" cy="2" r="0" fill="none" style="stroke:var(--g)" stroke-width="2"/>`;
  layer.appendChild(c);
  return c;
}

export async function showMe(cur: SVGSVGElement, to: Pt, path: Pt[] | undefined, click: string, W: number, H: number) {
  const my = ++token;
  const alive = () => my === token;
  const ring = cur.querySelector<SVGCircleElement>(".ring")!;
  const put = (p: Pt, ms: number) => { cur.style.transitionDuration = `${ms}ms, 150ms`; cur.style.transform = `translate(${p[0] - 2}px,${p[1] - 2}px)`; };
  const pulse = async (n: number) => {
    for (let i = 0; i < n && alive(); i++) {
      for (let k = 0; k <= 8; k++) { ring.setAttribute("r", String(k * 1.6)); ring.setAttribute("opacity", String(1 - k / 9)); await sleep(18); }
      ring.setAttribute("r", "0");
      if (i < n - 1) await sleep(40);
    }
  };
  const target = path?.length ? path[0] : to;
  // Start a little down-right of the target (or up-left near the bottom-right corner).
  const sx = target[0] + (target[0] + 260 < W ? 220 : -220), sy = target[1] + (target[1] + 200 < H ? 160 : -160);
  put([sx, sy], 0);
  cur.style.opacity = "1";
  await sleep(30);
  put(target, MOVE_MS);
  await sleep(MOVE_MS + 60);
  if (!alive()) return;
  if (path && path.length > 1) {
    await pulse(1);
    for (const p of path.slice(1)) { put(p, 1200); await sleep(1260); if (!alive()) return; }
    await pulse(1);
  } else if (click !== "none") {
    await pulse(click === "double" ? 2 : 1);
  }
  await sleep(500);
  if (alive()) cur.style.opacity = "0";
}

export function cancelShowMe(cur?: SVGSVGElement) { token++; if (cur) cur.style.opacity = "0"; }
