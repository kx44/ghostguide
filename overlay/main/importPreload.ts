// The bridge for the import window (contextIsolation on, no Node in the page).
import { contextBridge, ipcRenderer, webUtils } from "electron";
import type { CompileDoneMsg, CompileProgressMsg, FromOverlay, ImportBridge } from "../shared/messages";

const ghostImport: ImportBridge = {
  on(cb: (m: CompileProgressMsg | CompileDoneMsg) => void) { ipcRenderer.on("import:msg", (_e, m) => cb(m)); },
  send(msg: FromOverlay) { ipcRenderer.send("ghost:send", msg); },
  pickFile() { return ipcRenderer.invoke("import:pick"); },
  pathOf(file: File) { return webUtils.getPathForFile(file); },
  close() { ipcRenderer.send("import:close"); },
};
contextBridge.exposeInMainWorld("ghostImport", ghostImport);
