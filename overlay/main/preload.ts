// The only bridge between a display's renderer and the main process (contextIsolation on, no Node in the page).
import { contextBridge, ipcRenderer } from "electron";
import type { FromOverlay, GhostBridge, HitRect, Routed } from "../shared/messages";

const ghost: GhostBridge = {
  on(cb: (r: Routed) => void) { ipcRenderer.on("ghost:msg", (_e, r: Routed) => cb(r)); ipcRenderer.send("ghost:ready"); },
  send(msg: FromOverlay) { ipcRenderer.send("ghost:send", msg); },
  setHitRects(rects: HitRect[]) { ipcRenderer.send("ghost:hits", rects); },
};
contextBridge.exposeInMainWorld("ghost", ghost);
