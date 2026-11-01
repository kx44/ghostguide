// The source window: the step's clip or section of the original tutorial. It's a normal window, because you scroll,
// select and seek in it, which the overlay's own windows can't take. It opens WITHOUT focus, so typing stays in the
// app until you click it, and it keeps above the app, so you can watch while you work.
import { BrowserWindow, Rectangle, dialog, ipcMain, session, shell } from "electron";
import { join } from "node:path";
import type { Box, SourceViewMsg } from "../shared/messages";

export const SOURCE_TITLE = "GhostGuide: source";
const GAP = 12;
const PARTITION = "persist:ghost-page";      // the page window's cookies, apart from everything else in the overlay
export const PAGE_TITLE = "GhostGuide: page";
const PAGE_SIZE = { width: 900, height: 820 };
const SIZE = { video: { width: 660, height: 470 }, text: { width: 520, height: 620 } };

/** The corner of the screen's work area furthest from the target, so the window doesn't cover what you're about to do. */
export function cornerAway(area: Rectangle, size: { width: number; height: number }, target?: Box): Rectangle {
  const left = area.x + GAP, right = area.x + area.width - size.width - GAP;
  const top = area.y + GAP, bottom = area.y + area.height - size.height - GAP;
  const cx = target ? target.x + target.w / 2 : area.x;
  const cy = target ? target.y + target.h / 2 : area.y + area.height;
  return { x: cx < area.x + area.width / 2 ? right : left, y: cy < area.y + area.height / 2 ? bottom : top, ...size };
}

/** A place you left it, kept on the screen it's opening on: a display can change between one open and the next. */
export function keepOnScreen(r: Rectangle, area: Rectangle): Rectangle {
  const width = Math.min(r.width, area.width), height = Math.min(r.height, area.height);
  return { width, height, x: Math.min(Math.max(r.x, area.x), area.x + area.width - width),
           y: Math.min(Math.max(r.y, area.y), area.y + area.height - height) };
}

/** A tutorial file is someone else's text: only web links may leave for the browser. */
export const isWebLink = (url: unknown): url is string => typeof url === "string" && /^https?:\/\/[^\s]+$/i.test(url);

export class SourceWindow {
  private win?: BrowserWindow;
  private page?: BrowserWindow;
  private pageBase?: string;
  private pageHeading?: string;
  private ready = false;
  private last?: SourceViewMsg;
  private bounds?: Rectangle;       // where you moved it to, this run; until then, the corner away from each step's target
  onChosen: (path: string) => void = () => {};
  onClosed: () => void = () => {};

  constructor(private workArea: () => Rectangle, private target: () => Box | undefined) {
    ipcMain.on("source:ready", e => {
      if (e.sender !== this.win?.webContents) return;
      this.ready = true;
      if (this.last) e.sender.send("source:msg", this.last);
    });
    ipcMain.on("source:link", (e, url) => { if (e.sender === this.win?.webContents && isWebLink(url)) void shell.openExternal(url); });
    ipcMain.on("source:page", (e, url, heading) => {
      if (e.sender === this.win?.webContents && isWebLink(url)) this.showPage(url, typeof heading === "string" ? heading : undefined);
    });
    ipcMain.on("source:close", () => this.close());
    ipcMain.on("source:choose", async (_e, kind: "video" | "page") => {
      const extensions = kind === "video" ? ["mp4", "mkv", "webm", "mov", "avi"] : ["html", "htm", "txt", "md"];
      const opts = { properties: ["openFile" as const], filters: [{ name: kind === "video" ? "Video" : "Saved page or text", extensions }] };
      const got = this.win ? await dialog.showOpenDialog(this.win, opts) : await dialog.showOpenDialog(opts);
      if (!got.canceled && got.filePaths[0]) this.onChosen(got.filePaths[0]);
    });
  }

  get isOpen() { return !!this.win && !this.win.isDestroyed(); }

  show(m: SourceViewMsg) {
    if (m.follow && !this.isOpen) return;       // closed while the answer was on its way
    this.last = m;
    if (!this.isOpen) this.open(m);
    else if (this.ready) this.win!.webContents.send("source:msg", m);
    if (m.link && m.where && this.page && !this.page.isDestroyed()) this.showPage(m.link, m.where);     // it follows the step
  }

  close() { if (this.isOpen) this.win!.close(); }

  /** The tutorial's real page, pictures and all, in a window you asked for: an ordinary browser window with no bridge to us. It
   *  stays beside the source window and follows the step. A site that wants a person to prove themselves asks you, there. */
  private showPage(url: string, heading?: string) {
    const base = url.split("#")[0];
    this.pageHeading = heading;
    if (this.page && !this.page.isDestroyed()) {
      if (this.pageBase === base) void this.scrollTo();
      else this.loadPage(url);
      this.page.showInactive();
      return;
    }
    session.fromPartition(PARTITION).setPermissionRequestHandler((_wc, _perm, answer) => answer(false));
    const beside = this.win?.getBounds();
    const area = this.workArea();
    const width = Math.min(PAGE_SIZE.width, area.width - 2 * GAP), height = Math.min(PAGE_SIZE.height, area.height - 2 * GAP);
    const page = new BrowserWindow({
      ...keepOnScreen({ width, height, x: beside ? beside.x - width - GAP : area.x + GAP, y: beside ? beside.y : area.y + GAP }, area),
      title: PAGE_TITLE, autoHideMenuBar: true, show: false, fullscreenable: false,
      webPreferences: { partition: PARTITION, contextIsolation: true, nodeIntegration: false, sandbox: true },
    });
    page.setAlwaysOnTop(true, "pop-up-menu");
    page.webContents.setAudioMuted(true);
    page.webContents.on("will-navigate", (e, to) => { if (!isWebLink(to)) e.preventDefault(); });
    page.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    page.on("page-title-updated", e => e.preventDefault());    // the engine must never take this for the app
    page.once("ready-to-show", () => page.showInactive());
    // Every load: a site's own check can come first, and the page you wanted loads after it.
    page.webContents.on("did-finish-load", () => void this.scrollTo());
    page.on("closed", () => { this.page = undefined; });
    this.page = page;
    this.loadPage(url);
  }

  private loadPage(url: string) {
    this.pageBase = url.split("#")[0];
    this.page!.loadURL(this.pageBase).catch(() => {});
  }

  /** To the step's section, going by its heading's words. Nothing is read back from the page. */
  private async scrollTo() {
    if (!this.pageHeading || !this.page || this.page.isDestroyed()) return;
    const words = JSON.stringify(this.pageHeading.trim().toLowerCase());
    await this.page.webContents.executeJavaScript(
      `[...document.querySelectorAll("h1,h2,h3,h4,h5")].find(h => h.textContent.trim().toLowerCase().includes(${words}))?.scrollIntoView(); 0`).catch(() => {});
  }

  private open(m: SourceViewMsg) {
    const size = m.kind === "text" || m.kind === "loading" ? SIZE.text : SIZE.video;
    const win = new BrowserWindow({
      ...(this.bounds ? keepOnScreen(this.bounds, this.workArea()) : cornerAway(this.workArea(), size, this.target())),
      minWidth: 360, minHeight: 280, title: SOURCE_TITLE, backgroundColor: "#17151D", autoHideMenuBar: true, show: false,
      minimizable: true, maximizable: false, fullscreenable: false,
      webPreferences: { preload: join(__dirname, "sourcePreload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true,
                        autoplayPolicy: "no-user-gesture-required" },
    });
    win.setAlwaysOnTop(true, "pop-up-menu");
    win.webContents.on("will-navigate", e => e.preventDefault());
    win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
    win.on("page-title-updated", e => e.preventDefault());     // the engine looks for this title, and never reads this window
    win.loadFile(join(__dirname, "..", "renderer", "source.html"));
    win.once("ready-to-show", () => win.showInactive());
    // Only when you move it: read back and reopened at a scaled display, a window grows a little each time.
    for (const ev of ["moved", "resized"] as const) win.on(ev as "moved", () => { this.bounds = win.getBounds(); });
    win.on("closed", () => {
      this.win = undefined; this.ready = false;
      if (this.page && !this.page.isDestroyed()) this.page.close();
      this.onClosed();
    });
    this.win = win;
  }
}
