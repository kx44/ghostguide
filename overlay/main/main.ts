// GhostGuide overlay, main process: one transparent, always-on-top, click-through window per display.
// It routes each engine message to the display its target is on, converted to that window's DIPs.
//
//   npm start                         connect to the engine at ws://127.0.0.1:8765 (python -m engine play …)
//   npm start -- --replay f.jsonl     a recorded session, no engine: step by step, waits for Next
//                                     [--timed [--speed 2] [--loop]] plays it on its timestamps instead
//   npm start -- --import             also open the import window (Ctrl+Alt+I any time)
import { BrowserWindow, Display, app, clipboard, dialog, ipcMain, screen, session } from "electron";
import { join } from "node:path";
import type { FromOverlay, HitRect, Local, Routed, StateMsg, ToOverlay } from "../shared/messages";
import { Link, connectEngine, replaySteps, replayTimed } from "./bridge";
import { displayForPoint, displayForRect, physicalDisplays, toDipPoint, toDipRect } from "./displays";
import { keyHints, registerHotkeys, unregisterHotkeys } from "./hotkeys";
import { loadSettings, saveSettings } from "./settings";
import { SourceWindow } from "./sourceWindow";
import { GhostTray } from "./tray";

const argv = process.argv.slice(1);
const arg = (name: string) => { const i = argv.indexOf(name); return i >= 0 ? argv[i + 1] : undefined; };
const REPLAY = arg("--replay");
const SPEED = Number(arg("--speed") ?? 1);
const LOOP = argv.includes("--loop");
const TIMED = argv.includes("--timed");
const ENGINE = arg("--engine") ?? `ws://127.0.0.1:${arg("--port") ?? 8765}`;
const HIT_POLL_MS = 30;          // cursor check for click-through (see ghost:hits)
const IMPORT_W = 480, IMPORT_H = 500;
const DEV = argv.includes("--dev") || !!process.env.GHOST_DEV;      // the pin keys
const SETTINGS = process.env.GG_SETTINGS ?? join(app.getPath("appData"), "GhostGuide", "overlay-settings.json");

interface Win { win: BrowserWindow; display: Display; ready: boolean; queue: Routed[]; hits: HitRect[]; clickable: boolean }
const wins = new Map<number, Win>();
let link: Link | undefined;
let lastState: StateMsg | undefined;
let guideDisplay: number | undefined;     // where the current step's guidance is drawn
let importWin: BrowserWindow | undefined;
let sourceWin: SourceWindow | undefined;
let tray: GhostTray | undefined;
let settings = loadSettings(SETTINGS);
let failedKeys: string[] = [];
let engineUp = !!REPLAY;
let targetBox: { x: number; y: number; w: number; h: number } | undefined;    // this step's target, screen DIPs
let sourceStep: number | undefined;       // the step the source window is showing

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
  win.webContents.on("will-navigate", e => e.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
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

/** The one window that takes focus: you type a link into it. It stays above the overlay and goes when closed. */
function openImport() {
  if (importWin && !importWin.isDestroyed()) { importWin.show(); importWin.focus(); return; }
  const win = new BrowserWindow({
    width: IMPORT_W, height: IMPORT_H, resizable: false, minimizable: true, maximizable: false, fullscreenable: false,
    title: "GhostGuide: import a tutorial", backgroundColor: "#17151D", autoHideMenuBar: true, show: false,
    webPreferences: { preload: join(__dirname, "importPreload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.setAlwaysOnTop(true, "pop-up-menu");
  win.webContents.on("will-navigate", e => e.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.loadFile(join(__dirname, "..", "renderer", "import.html"));
  win.once("ready-to-show", () => win.show());
  win.on("closed", () => { importWin = undefined; });
  importWin = win;
}

function toggleSource() {
  if (sourceWin?.isOpen) return sourceWin.close();
  if (!engineUp || !lastState) return route({ type: "toast", text: "Open a tutorial first: it has nothing to show yet.", kind: "warn", ms: 2500 });
  link?.send({ type: "source" });
}

function sendShell(w: Win) {
  w.win.webContents.send("ghost:shell", { keyBar: settings.keyBar, keys: keyHints(failedKeys) });
}

function setKeyBar(show: boolean) {
  settings = { ...settings, keyBar: show };
  saveSettings(SETTINGS, settings);
  for (const w of wins.values()) if (w.ready) sendShell(w);
  tray?.update();
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
      targetBox = local.box && { ...local.box, x: local.box.x + target.display.bounds.x, y: local.box.y + target.display.bounds.y };
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
      if (sourceWin?.isOpen && !msg.finished && msg.current !== sourceStep) {   // the source follows the step
        sourceStep = msg.current;
        link?.send({ type: "source", follow: true });
      }
      tray?.update();
      break;
    case "source_view":
      sourceStep = msg.n;
      sourceWin?.show(msg);
      tray?.update();
      break;
    case "compile_progress":
    case "compile_done":
      if (importWin && !importWin.isDestroyed()) importWin.webContents.send("import:msg", msg);
      else if (msg.type === "compile_done") route({ type: "toast", text: msg.ok ? `Compiled: ${msg.title}` : `Compile stopped: ${msg.error}`, kind: msg.ok ? "ok" : "warn", ms: 5000 });
      break;
    default:
      deliver(primaryWin(), msg);
  }
}

function hello() {
  link?.send({ type: "hello", displays: physicalDisplays(), version: app.getVersion(), replay: !!REPLAY });
}

app.whenReady().then(() => {
  // Nothing here needs the camera, the microphone or a screen grab: the engine does its own looking.
  session.defaultSession.setPermissionRequestHandler((_wc, _perm, answer) => answer(false));
  buildWindows();
  ipcMain.on("ghost:ready", e => {
    const w = [...wins.values()].find(x => x.win.webContents === e.sender);
    if (!w) return;
    w.ready = true;
    sendShell(w);
    for (const r of w.queue.splice(0)) w.win.webContents.send("ghost:msg", r);
  });
  ipcMain.on("ghost:send", (e, msg: FromOverlay) => {      // the overlay's own windows and the import window; never the source window
    if ([...wins.values()].some(x => x.win.webContents === e.sender) || importWin?.webContents === e.sender) link?.send(msg);
  });
  ipcMain.on("ghost:copy", (_e, text: string) => { if (typeof text === "string") clipboard.writeText(text); });
  ipcMain.on("ghost:source", () => toggleSource());
  ipcMain.on("ghost:keybar", (_e, show: boolean) => setKeyBar(!!show));
  sourceWin = new SourceWindow(
    () => screen.getDisplayMatching(targetBox ? { x: targetBox.x, y: targetBox.y, width: targetBox.w, height: targetBox.h }
                                              : primaryWin().display.bounds).workArea,
    () => targetBox);
  sourceWin.onChosen = path => link?.send({ type: "source_file", path });
  sourceWin.onClosed = () => { sourceStep = undefined; tray?.update(); };
  ipcMain.on("import:close", () => importWin?.close());
  ipcMain.handle("import:pick", async () => {
    const opts = { properties: ["openFile" as const], filters: [
      { name: "Tutorials", extensions: ["html", "htm", "txt", "md", "mp4", "mkv", "webm", "mov", "avi"] }] };
    const got = importWin ? await dialog.showOpenDialog(importWin, opts) : await dialog.showOpenDialog(opts);
    return got.canceled ? undefined : got.filePaths[0];
  });
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
        engineUp = up;
        tray?.update();
        console.log(up ? `connected to engine ${ENGINE}` : `engine not reachable at ${ENGINE}, retrying every second`);
        if (!up) {
          route({ type: "clear" });
          route({ type: "toast", text: "Waiting for the engine: python -m engine play <tutorial.md>", kind: "warn", ms: 4000 });
        }
      });

  const failed = registerHotkeys(() => !!lastState?.hidden, {
    send: m => link?.send(m), quit: () => app.quit(), openImport, toggleSource, toggleKeyBar: () => setKeyBar(!settings.keyBar),
  }, DEV);
  failedKeys = failed;
  for (const w of wins.values()) if (w.ready) sendShell(w);
  tray = new GhostTray(() => ({ state: lastState, engineUp, keyBar: settings.keyBar, sourceOpen: !!sourceWin?.isOpen }), {
    hideResume: () => link?.send({ type: lastState?.hidden ? "resume" : "hide" }),
    next: () => link?.send({ type: "next" }),
    back: () => link?.send({ type: "back" }),
    source: toggleSource,
    scheme: () => link?.send({ type: "toggle_scheme" }),
    localOnly: () => link?.send({ type: "toggle_local" }),
    importTutorial: openImport,
    setKeyBar,
    quit: () => app.quit(),
  });
  if (argv.includes("--import")) openImport();
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

app.on("will-quit", () => { unregisterHotkeys(); tray?.destroy(); link?.close(); });
app.on("window-all-closed", () => app.quit());
