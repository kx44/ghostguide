// Renderer for one display's overlay window. It only draws what the engine says; it never decides.
// main.ts has already converted the message's geometry into this window's DIPs (`local`).
import type { FromOverlay, GhostBridge, GuideMsg, Local, Routed, StateMsg, Style } from "../shared/messages";
import { Ctx, Mounted, toRect } from "./dom";
import { mountBeacon } from "./guidance/beacon";
import { fallbackHtml, mountCard } from "./guidance/card";
import { mountClickType } from "./guidance/clickType";
import { mountCodeCard } from "./guidance/codeCard";
import { mountGhostLine } from "./guidance/ghostLine";
import { mountGhostText } from "./guidance/ghostText";
import { mountKeycaps } from "./guidance/keycaps";
import { mountMask } from "./guidance/mask";
import { mountOffscreen } from "./guidance/offscreen";
import { mountOutline } from "./guidance/outline";
import { mountPathChips } from "./guidance/pathChips";
import { cancelShowMe, ghostCursor, showMe } from "./guidance/showMe";
import { mountSignalCard } from "./guidance/signalCard";
import { mountTaskbar } from "./guidance/taskbar";
import { toast } from "./guidance/toast";
import { ControlBar } from "./shell/controlBar";
import { StartCheck } from "./shell/startCheck";
import { StepRail } from "./shell/stepRail";

declare global { interface Window { ghost: GhostBridge } }

type Mount = (ctx: Ctx, g: GuideMsg, local: Local) => Mounted;
const STYLE: Record<Style, Mount> = {
  outline: mountOutline,
  ghost_line: (c, g, l) => mountGhostLine(c, g, l, true),
  beacon: mountBeacon,
  static_line: (c, g, l) => mountGhostLine(c, g, l, false),
  code_card: mountCodeCard,
  ghost_text: mountGhostText,     // KIV: unused (code_card replaced it), kept for later
  keycaps: mountKeycaps,
  mask: mountMask,
  path_chips: mountPathChips,
  offscreen: mountOffscreen,
  taskbar: mountTaskbar,
  click_type: mountClickType,
  signal_card: mountSignalCard,
  card: (_c, g, l) => { const f = fallbackHtml(g); return { anchor: toRect(l.box), cardTop: f.top, cardHtml: f.body, wide: !!f.top, remove() {} }; },
};

const $ = (id: string) => document.getElementById(id)!;
const root = $("root"), ov = $("ov"), geo = $("geo") as unknown as SVGSVGElement, fx = $("fx"), toasts = $("toasts"), shell = $("shell");
const bridge = window.ghost;
const send = (m: FromOverlay) => bridge.send(m);

let mounted: Mounted | undefined;
let card: HTMLDivElement | undefined;
let lastGuide: { g: GuideMsg; local: Local } | undefined;
let lastState: StateMsg | undefined;
let isPrimary = false;
let holdUntil = 0;              // after a success mark, keep the green outline briefly before the next step
let pending: ReturnType<typeof setTimeout> | undefined;
const cursor = ghostCursor(fx);
const bar = new ControlBar(shell, send);
const rail = new StepRail(shell, send);
const startCheck = new StartCheck(shell, send);
bar.onToggleRail = () => { rail.open = !rail.open; if (lastState) { bar.render(lastState, rail.open); rail.render(lastState); } };

function ctx(): Ctx { return { ov, svg: geo, W: window.innerWidth, H: window.innerHeight }; }
const bottomReserve = () => (isPrimary ? 110 : 60);

function clearGuide() {
  mounted?.remove(); mounted = undefined;
  card?.remove(); card = undefined;
  ov.innerHTML = ""; geo.innerHTML = "";
  cancelShowMe(cursor);
}

function drawGuide(g: GuideMsg, local: Local) {
  clearGuide();
  root.dataset.scheme = g.scheme;
  lastGuide = { g, local };
  const mount = STYLE[g.style] ?? STYLE.card;
  try {
    mounted = mount(ctx(), g, local);
  } catch (e) {
    console.error(`style ${g.style} failed, showing the card alone`, e);
    mounted = STYLE.card(ctx(), g, local);
  }
  if (g.card) card = mountCard(ctx(), g, g.card, mounted, onCardAction, bottomReserve(), local.avoid ?? []);
}

function onCardAction(a: string, btn: HTMLElement) {
  if (a === "skip_wait") return send({ type: "next" });
  if (a === "show_me") { btn.classList.add("pri"); setTimeout(() => btn.classList.remove("pri"), 1600); }
  send({ type: a } as FromOverlay);
}

function onMessage(r: Routed) {
  const m = r.msg;
  isPrimary = r.primary;
  switch (m.type) {
    case "guide": {
      startCheck.clear();
      const wait = holdUntil - Date.now();
      if (pending) clearTimeout(pending);
      if (wait > 0) pending = setTimeout(() => drawGuide(m, r.local), wait);
      else drawGuide(m, r.local);
      break;
    }
    case "clear":
      if (pending) clearTimeout(pending);
      clearGuide();
      if (m.reason !== "capture") startCheck.clear();
      lastGuide = undefined;
      break;
    case "start_check":
      startCheck.render(m);
      break;
    case "mark":
      mounted?.mark?.(m.result);
      if (m.result === "ok") holdUntil = Date.now() + 350;
      break;
    case "show_me":
      if (r.local.to) void showMe(cursor, r.local.to, r.local.path, m.click, window.innerWidth, window.innerHeight);
      break;
    case "toast":
      toast(toasts, m.text, m.kind, m.ms, bottomReserve() + 12);
      break;
    case "state":
      lastState = m;
      if (!lastGuide) root.dataset.scheme = m.scheme;
      if (r.primary) { bar.render(m, rail.open); rail.render(m); }
      break;
    default:
      break;     // compile_progress (phase 5)
  }
}

// Clicks pass through everywhere except our own cards and buttons (`.hit`). This page reports where those
// are and main.ts watches the cursor, turning mouse events on for this window only while it's over one.
// (Turning them on from forwarded mousemove events here didn't work on Windows: a click-through window
// gets no moves.) The window never takes focus, so typing stays in the app.
let lastHits = "";
function reportHits() {
  const rects = [...document.querySelectorAll<HTMLElement>(".hit")].map(e => e.getBoundingClientRect())
    .filter(r => r.width > 0 && r.height > 0)
    .map(r => ({ x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) }));
  const key = JSON.stringify(rects);
  if (key !== lastHits) { lastHits = key; bridge.setHitRects(rects); }
}
setInterval(reportHits, 100);     // cheap, and catches cards that move, animate in or get removed
window.addEventListener("ghost:hits", reportHits);   // right away, e.g. when a card drag starts

window.addEventListener("resize", () => { if (lastGuide && !pending) drawGuide(lastGuide.g, lastGuide.local); });

bridge.on(onMessage);
