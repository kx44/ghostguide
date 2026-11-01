// The bridge for the source window (contextIsolation on, no Node in the page).
import { contextBridge, ipcRenderer } from "electron";
import type { PageState, SourceBridge, SourceViewMsg } from "../shared/messages";

const ghostSource: SourceBridge = {
  on(cb: (m: SourceViewMsg) => void) { ipcRenderer.on("source:msg", (_e, m) => cb(m)); ipcRenderer.send("source:ready"); },
  showPage(url: string, section?: string, words?: string[]) { ipcRenderer.send("source:page", url, section, words); },
  hidePage() { ipcRenderer.send("source:page-off"); },
  pageArea(r) { ipcRenderer.send("source:page-area", r); },
  onPage(cb: (state: PageState) => void) { ipcRenderer.on("source:page-state", (_e, s) => cb(s)); },
  openLink(url: string) { ipcRenderer.send("source:link", url); },
  choose(kind: "video" | "page") { ipcRenderer.send("source:choose", kind); },
  close() { ipcRenderer.send("source:close"); },
};
contextBridge.exposeInMainWorld("ghostSource", ghostSource);
