// The only bridge between a display's renderer and the main process (contextIsolation on, no Node in the page).
import { contextBridge, ipcRenderer } from "electron";
import type { FromOverlay, GhostBridge, HitRect, Routed, ShellInfo } from "../shared/messages";

const ghost: GhostBridge = {
  on(cb: (r: Routed) => void) { ipcRenderer.on("ghost:msg", (_e, r: Routed) => cb(r)); ipcRenderer.send("ghost:ready"); },
  send(msg: FromOverlay) { ipcRenderer.send("ghost:send", msg); },
  setHitRects(rects: HitRect[]) { ipcRenderer.send("ghost:hits", rects); },
  copy(text: string) { ipcRenderer.send("ghost:copy", text); },
  toggleSource() { ipcRenderer.send("ghost:source"); },
  onShell(cb: (s: ShellInfo) => void) { ipcRenderer.on("ghost:shell", (_e, s: ShellInfo) => cb(s)); },
  setKeyBar(show: boolean) { ipcRenderer.send("ghost:keybar", show); },
};
contextBridge.exposeInMainWorld("ghost", ghost);
