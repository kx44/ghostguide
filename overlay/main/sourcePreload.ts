// The bridge for the source window (contextIsolation on, no Node in the page).
import { contextBridge, ipcRenderer } from "electron";
import type { SourceBridge, SourceViewMsg } from "../shared/messages";

const ghostSource: SourceBridge = {
  on(cb: (m: SourceViewMsg) => void) { ipcRenderer.on("source:msg", (_e, m) => cb(m)); ipcRenderer.send("source:ready"); },
  loadPictures(url: string) { return ipcRenderer.invoke("source:pictures", url); },
  openLink(url: string) { ipcRenderer.send("source:link", url); },
  choose(kind: "video" | "page") { ipcRenderer.send("source:choose", kind); },
  close() { ipcRenderer.send("source:close"); },
};
contextBridge.exposeInMainWorld("ghostSource", ghostSource);
