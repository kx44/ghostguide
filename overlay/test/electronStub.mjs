// Stands in for Electron in the unit tests: they only touch plain functions, never these.
const nothing = {};
export const session = nothing, BrowserWindow = nothing, Menu = nothing, Tray = nothing, dialog = nothing, globalShortcut = nothing, ipcMain = nothing,
  nativeImage = nothing, screen = nothing, shell = nothing, app = nothing;
