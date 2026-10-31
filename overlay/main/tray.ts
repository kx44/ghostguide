// The tray icon: GhostGuide has no window of its own to find, so this is where it lives while it runs.
import { Menu, MenuItemConstructorOptions, Tray, nativeImage } from "electron";
import { join } from "node:path";
import type { StateMsg } from "../shared/messages";

export interface TrayActions {
  hideResume(): void;
  next(): void;
  back(): void;
  source(): void;
  scheme(): void;
  importTutorial(): void;
  setKeyBar(show: boolean): void;
  quit(): void;
}
export interface TrayView { state?: StateMsg; engineUp: boolean; keyBar: boolean; sourceOpen: boolean }

/** The hover text and the top line of the menu. */
export function trayStatus(v: Pick<TrayView, "state" | "engineUp">): string {
  if (!v.engineUp) return "Waiting for the engine";
  if (!v.state) return "No tutorial open";
  const s = v.state;
  if (s.finished) return `${s.tutorial}: finished`;
  return `${s.hidden ? "Paused at step" : "Step"} ${s.current} of ${s.of}`;
}

export function trayMenu(v: TrayView, a: TrayActions): MenuItemConstructorOptions[] {
  const s = v.state;
  const playing = v.engineUp && !!s && !s.finished;
  return [
    { label: `GhostGuide · ${trayStatus(v)}`, enabled: false },
    { type: "separator" },
    { label: s?.hidden ? "Resume" : "Hide", accelerator: "Ctrl+Alt+H", enabled: playing, registerAccelerator: false, click: a.hideResume },
    { label: "Next step", accelerator: "Ctrl+Alt+Right", enabled: playing && !s?.hidden, registerAccelerator: false, click: a.next },
    { label: "Back", accelerator: "Ctrl+Alt+Left", enabled: playing && !s?.hidden && (s?.current ?? 1) > 1, registerAccelerator: false, click: a.back },
    { label: v.sourceOpen ? "Close the source" : "Open this step's source", accelerator: "Ctrl+Alt+O", enabled: v.engineUp && !!s, registerAccelerator: false, click: a.source },
    { label: "Light / dark", accelerator: "Ctrl+Alt+D", enabled: playing, registerAccelerator: false, click: a.scheme },
    { type: "separator" },
    { label: "Import a tutorial…", accelerator: "Ctrl+Alt+I", registerAccelerator: false, click: a.importTutorial },
    { label: "Show the shortcuts", type: "checkbox", checked: v.keyBar, accelerator: "Ctrl+Alt+K", registerAccelerator: false, click: item => a.setKeyBar(item.checked) },
    { type: "separator" },
    { label: "Quit GhostGuide", accelerator: "Ctrl+Alt+Q", registerAccelerator: false, click: a.quit },
  ];
}

/** Everything the icon and menu show: the same key means nothing to redraw. */
export const trayKey = (v: TrayView) =>
  JSON.stringify([v.engineUp, v.keyBar, v.sourceOpen, v.state?.tutorial, v.state?.current, v.state?.of, v.state?.hidden, v.state?.finished]);

export class GhostTray {
  private shown?: string;
  private tray: Tray;
  private icons = { on: nativeImage.createFromPath(join(__dirname, "..", "assets", "tray.ico")),
                    paused: nativeImage.createFromPath(join(__dirname, "..", "assets", "tray-paused.ico")) };

  constructor(private view: () => TrayView, private actions: TrayActions) {
    this.tray = new Tray(this.icons.on);
    this.tray.on("click", () => this.tray.popUpContextMenu());     // the menu on either button: there's nothing else to open
    this.update();
  }

  /** The engine sends its state many times a step, and each of these calls waits on the Windows shell: only when it shows. */
  update() {
    const v = this.view();
    const now = trayKey(v);
    if (now === this.shown) return;
    this.shown = now;
    this.tray.setImage(v.state?.hidden || !v.engineUp ? this.icons.paused : this.icons.on);
    this.tray.setToolTip(`GhostGuide · ${trayStatus(v)}`);
    this.tray.setContextMenu(Menu.buildFromTemplate(trayMenu(v, this.actions)));
  }

  destroy() { this.tray.destroy(); }
}
