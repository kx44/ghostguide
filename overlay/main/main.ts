// GhostGuide overlay, main process: one transparent, always-on-top, click-through window per display.
// It routes each engine message to the display its target is on, converted to that window's DIPs.
//
//   npm start                         connect to the engine at ws://127.0.0.1:8765 (python -m engine play …)
//   npm start -- --replay f.jsonl     a recorded session, no engine: step by step, waits for Next
//                                     [--timed [--speed 2] [--loop]] plays it on its timestamps instead
import { BrowserWindow, Display, app, clipboard, ipcMain, screen } from "electron";
import { join } from "node:path";
import type { FromOverlay, HitRect, Local, Routed, StateMsg, ToOverlay } from "../shared/messages";
import { Link, connectEngine, replaySteps, replayTimed } from "./bridge";
import { displayForPoint, displayForRect, physicalDisplays, toDipPoint, toDipRect } from "./displays";
import { registerHotkeys, unregisterHotkeys } from "./hotkeys";

const argv = process.argv.slice(1);
const arg = (name: string) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : undefined; };
const REPLAY = arg("--replay");
const SPEED = Number(arg("--speed") ?? 1);
const LOOP = argv.includes("--loop");
const TIMED = argv.includes("--timed");
const ENGINE = arg("--engine") ?? `ws://127.0.0.1:${arg("--port") ?? 8765}`;
const HIT_POLL_MS = 30;          // cursor check for click-through (see ghost:hits)

interface Win { win: BrowserWindow; display: Display; ready: boolean; queue: Routed[]; hits: HitRect[]; clickable: boolean }
const wins = new Map<number, Win>();
let link: Link | undefined;
let lastState: StateMsg | undefined;
let guideDisplay: number | undefined;     // where the current step's guidance is drawn

if (!app.requestSingleInstanceLock()) app.quit();

function makeWindow(d: Display): Win {
  const win = new BrowserWindow({
    x: d.bounds.x, y: d.bounds.y, width: d.bounds.width, height: d.bounds.height,
    transparent: true, frame: false, resizable: false, movable: false, minimizable: false, maximizable: false,
    fullscreenable: false, skipTaskbar: true, hasShadow: false, focusable: false, show: false,
    backgroundColor: "#00000000", alwaysOnTop: true,
    webPreferences: { preload: join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false,
                      sandbox: true, backgroundThrottling: false },
  });
  win.setAlwaysOnTop(true, "screen-saver");      // above the taskbar too (style 10 outlines a taskbar icon)
  win.setIgnoreMouseEvents(true, { forward: true });
  win.setVisibleOnAllWorkspaces(true);
  win.setBounds(d.bounds);                        // Windows can shrink a frameless window on a scaled display
  const w: Win = { win, display: d, ready: false, queue: [], hits: [], clickable: false };
  win.loadFile(join(__dirname, "..", "renderer", "index.html"));
  win.once("ready-to-show", () => win.showInactive());
  win.webContents.on("render-process-gone", (_e, det) => console.error("overlay renderer gone:", det.reason));
  return w;
}

function buildWindows() {
  const displays = screen.getAllDisplays();
  for (const [id, w] of wins) if (!displays.find(d => d.id === id)) { w.win.destroy(); wins.delete(id); }
  for (const d of displays) {
    const w = wins.get(d.id);
    if (w) { w.display = d; w.win.setBounds(d.bounds); } else wins.set(d.id, makeWindow(d));
  }
}

function deliver(w: Win, msg: ToOverlay, local: Local = {}) {
  const r: Routed = { msg, local, primary: w.display.id === screen.getPrimaryDisplay().id,
                      display: { w: w.display.bounds.width, h: w.display.bounds.height } };
  if (w.ready) w.win.webContents.send("ghost:msg", r); else w.queue.push(r);
}

const localRect = (d: Display, x: number, y: number, width: number, height: number) =>
  ({ x: Math.round(x - d.bounds.x), y: Math.round(y - d.bounds.y), w: Math.round(width), h: Math.round(height) });
const localPt = (d: Display, p: [number, number]): [number, number] => [Math.round(p[0] - d.bounds.x), Math.round(p[1] - d.bounds.y)];
const primaryWin = () => wins.get(screen.getPrimaryDisplay().id) ?? [...wins.values()][0];

function route(msg: ToOverlay) {
  if (process.env.GHOST_DEBUG) console.log("route", msg.type, wins.size);
  switch (msg.type) {
    case "guide": {
      let d: Display | undefined, local: Local = {};
      if (msg.style === "offscreen" && msg.extra.edge_point) {
        const p = toDipPoint(msg.extra.edge_point);
        d = displayForPoint(p);
        local.edge_point = localPt(d, p);
      } else if (msg.line) {
        const a = toDipPoint(msg.line.from), b = toDipPoint(msg.line.to);
        d = displayForPoint([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
        local.line = { from: localPt(d, a), to: localPt(d, b) };
      }
      if (msg.box) {
        const r = toDipRect(msg.box);
        d = d ?? displayForRect(r);
        local.box = localRect(d, r.x, r.y, r.width, r.height);
      }
      if (msg.extra.clip && d) {
        const c = toDipRect(msg.extra.clip);
        local.clip = localRect(d, c.x, c.y, c.width, c.height);
      }
      if (msg.extra.avoid?.length && d) {
        const dd = d;
        local.avoid = msg.extra.avoid.map(a => { const r = toDipRect(a); return localRect(dd, r.x, r.y, r.width, r.height); });
      }
      const target = (d && wins.get(d.id)) || (guideDisplay !== undefined && wins.get(guideDisplay)) || primaryWin();
      guideDisplay = target.display.id;
      for (const w of wins.values()) deliver(w, w === target ? msg : { type: "clear" }, w === target ? local : {});
      break;
    }
    case "show_me": {
      const w = (guideDisplay !== undefined && wins.get(guideDisplay)) || primaryWin();
      const local: Local = { to: localPt(w.display, toDipPoint(msg.to)) };
      if (msg.path) local.path = msg.path.map(p => localPt(w.display, toDipPoint(p)));
      deliver(w, msg, local);
      break;
    }
    case "mark":
    case "toast": {
      deliver((guideDisplay !== undefined && wins.get(guideDisplay)) || primaryWin(), msg);
      break;
    }
    case "clear":
      for (const w of wins.values()) deliver(w, msg);
      break;
    case "state":
      lastState = msg;
      for (const w of wins.values()) deliver(w, msg);     // every window needs the scheme; only primary draws the shell
      break;
    default:
      deliver(primaryWin(), msg);
  }
}

function hello() {
  link?.send({ type: "hello", displays: physicalDisplays(), version: app.getVersion(), replay: !!REPLAY });
}

app.whenReady().then(() => {
  buildWindows();
  ipcMain.on("ghost:ready", e => {
    const w = [...wins.values()].find(x => x.win.webContents === e.sender);
    if (!w) return;
    w.ready = true;
    for (const r of w.queue.splice(0)) w.win.webContents.send("ghost:msg", r);
  });
  ipcMain.on("ghost:send", (_e, msg: FromOverlay) => link?.send(msg));
  ipcMain.on("ghost:copy", (_e, text: string) => { if (typeof text === "string") clipboard.writeText(text); });
  ipcMain.on("ghost:hits", (e, rects: HitRect[]) => {
    const w = [...wins.values()].find(x => x.win.webContents === e.sender);
    if (w) w.hits = rects;
  });
  // Clickable only while the cursor is over a card or button of that window; click-through everywhere else.
  setInterval(() => {
    const p = screen.getCursorScreenPoint();
    for (const w of wins.values()) {
      const x = p.x - w.display.bounds.x, y = p.y - w.display.bounds.y;
      const over = w.hits.some(r => x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h);
      if (over !== w.clickable) { w.clickable = over; w.win.setIgnoreMouseEvents(!over, { forward: true }); }
    }
  }, HIT_POLL_MS);

  let wasUp: boolean | undefined;
  link = REPLAY
    ? (TIMED ? replayTimed(REPLAY, route, SPEED, LOOP) : replaySteps(REPLAY, route))
    : connectEngine(ENGINE, route, hello, up => {
        if (up === wasUp) return;
        wasUp = up;
        console.log(up ? `connected to engine ${ENGINE}` : `engine not reachable at ${ENGINE}, retrying every second`);
        if (!up) {
          route({ type: "clear" });
          route({ type: "toast", text: "Waiting for the engine: python -m engine play <tutorial.md>", kind: "warn", ms: 4000 });
        }
      });

  const failed = registerHotkeys(() => !!lastState?.hidden, m => link?.send(m), () => app.quit());
  if (failed.length) {
    console.warn("hotkeys taken by another app:", failed.join(", "));
    const keys = failed.map(a => a.replace("Control", "Ctrl").replace("Right", "→").replace("Left", "←")).join(", ");
    setTimeout(() => route({ type: "toast", text: `${keys} is used by another app; use the card or bar buttons instead.`,
                             kind: "warn", ms: 6000 }), 1500);
  }

  const rebuild = () => { buildWindows(); hello(); };
  screen.on("display-added", rebuild);
  screen.on("display-removed", rebuild);
  screen.on("display-metrics-changed", rebuild);
});

app.on("will-quit", () => { unregisterHotkeys(); link?.close(); });
app.on("window-all-closed", () => app.quit());
