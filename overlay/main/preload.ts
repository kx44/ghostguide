// The only bridge between a display's renderer and the main process (contextIsolation on, no Node in the page).
import { contextBridge, ipcRenderer } from "electron";
import type { FromOverlay, GhostBridge, Routed } from "../shared/messages";

const ghost: GhostBridge = {
  on(cb: (r: Routed) => void) { ipcRenderer.on("ghost:msg", (_e, r: Routed) => cb(r)); ipcRenderer.send("ghost:ready"); },
  send(msg: FromOverlay) { ipcRenderer.send("ghost:send", msg); },
  setInteractive(on: boolean) { ipcRenderer.send("ghost:interactive", on); },
};
contextBridge.exposeInMainWorld("ghost", ghost);
