// Unit tests for the overlay's plain logic: node test/unit.mjs (needs no window). Bundled first, because it's TypeScript.
import { build } from "esbuild";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const dir = mkdtempSync(join(tmpdir(), "gg-unit-"));
const out = join(dir, "logic.mjs");
await build({
  stdin: { contents: `export * from "./main/settings"; export * from "./main/hotkeys"; export { trayStatus, trayMenu, trayKey } from "./main/tray"; export { cornerAway, keepOnScreen, isWebLink, SOURCE_TITLE } from "./main/sourceWindow"; export { esc, kc } from "./renderer/dom"; export { codeBoxHtml } from "./renderer/guidance/codeCard"; export { chipsHtml } from "./renderer/guidance/pathChips"; export { keycapsHtml } from "./renderer/guidance/keycaps"; export { fallbackHtml } from "./renderer/guidance/card";`,
           resolveDir: process.cwd(), loader: "ts" },
  bundle: true, platform: "node", format: "esm", outfile: out, logLevel: "warning",
  alias: { electron: join(process.cwd(), "test", "electronStub.mjs") },
});
const L = await import(pathToFileURL(out));
process.on("exit", () => rmSync(dir, { recursive: true, force: true }));

test("a tutorial's text can't become markup in the overlay", () => {
  const evil = `<img src=x onerror=alert(1)>"'`;
  const clean = h => { assert.ok(!/<img/i.test(h), h); assert.ok(h.includes("&lt;img") || h === "", h); };
  clean(L.esc(evil));
  clean(L.kc(evil));
  clean(L.codeBoxHtml(evil, evil, evil, evil));
  clean(L.chipsHtml([evil, "ok"], 0));
  clean(L.keycapsHtml([evil]));
  const f = L.fallbackHtml({ extra: { path: [evil], keys: [evil], value: evil, action: "type" } });
  clean(f.top);
  clean(f.body);
  assert.equal(L.fallbackHtml({ extra: { action: "wait", signals: [evil] } }).body.includes("<img"), false);
  assert.ok(!/data-copy="[^"]*"[^>]*onerror/.test(L.codeBoxHtml(`" onerror="x`)));
});

test("tray: says what's happening to your screen, and the switch is there", () => {
  const a = { hideResume() {}, next() {}, back() {}, source() {}, scheme() {}, localOnly() {}, importTutorial() {}, setKeyBar() {}, quit() {} };
  const state = { tutorial: "T", current: 1, of: 2, hidden: false, finished: false, titles: [], statuses: [], scheme: "dark", privacy: "Nothing from your screen leaves this PC", local_only: true };
  const v = { state, engineUp: true, keyBar: false, sourceOpen: false };
  const menu = L.trayMenu(v, a);
  assert.ok(menu.some(i => i.label === state.privacy && i.enabled === false));
  const sw = menu.find(i => i.label === "Keep my screen on this PC");
  assert.equal(sw.type, "checkbox");
  assert.equal(sw.checked, true);
  assert.notEqual(L.trayKey(v), L.trayKey({ ...v, state: { ...state, privacy: "1 picture" } }));
});

test("settings: the panel starts closed, and a bad file changes nothing", () => {
  assert.deepEqual(L.parseSettings(undefined), { keyBar: false });
  assert.deepEqual(L.parseSettings("{not json"), { keyBar: false });
  assert.deepEqual(L.parseSettings('{"keyBar":"no"}'), { keyBar: false });
  assert.deepEqual(L.parseSettings("null"), { keyBar: false });
  assert.deepEqual(L.parseSettings('{"keyBar":true}'), { keyBar: true });
});

test("settings: the choice survives a restart", () => {
  const p = join(dir, "deep", "er", "s.json");
  assert.equal(L.loadSettings(p).keyBar, false);
  L.saveSettings(p, { keyBar: true });
  assert.equal(L.loadSettings(p).keyBar, true);
  writeFileSync(p, "garbage");
  assert.equal(L.loadSettings(p).keyBar, false);
});

test("hotkeys: one job each, all Ctrl+Alt, nothing that eats typing", () => {
  const accels = L.HOTKEYS.map(h => h.accel);
  assert.equal(new Set(accels).size, accels.length);
  for (const a of accels) assert.match(a, /^Control\+Alt\+\w+$/);
  assert.ok(!L.HOTKEYS.some(h => /do.?it/i.test(h.what)), "acting on your app takes a click");
});

test("hotkeys: the pin keys are for development only", () => {
  const keys = dev => L.activeHotkeys(dev).map(h => L.keyName(h.accel));
  assert.ok(!keys(false).includes("P") && !keys(false).includes("U"));
  assert.ok(keys(true).includes("P") && keys(true).includes("U"));
});

test("hotkey bar: shows every key a person has, marks one another app holds", () => {
  const hints = L.keyHints(["Control+Alt+O"]);
  assert.deepEqual(hints.map(h => h.key), ["→", "←", "S", "G", "O", "H", "D", "I", "K", "Q"]);
  assert.deepEqual(hints.filter(h => h.taken).map(h => h.label), ["Source"]);
});

const area = { x: 0, y: 0, width: 1706, height: 1020 };
const size = { width: 660, height: 470 };
const centre = r => [r.x + r.width / 2, r.y + r.height / 2];

test("source window: opens in the corner away from the target, inside the work area", () => {
  for (const [tx, ty, left, top] of [[10, 10, false, false], [1600, 10, true, false], [10, 900, false, true], [1600, 900, true, true]]) {
    const r = L.cornerAway(area, size, { x: tx, y: ty, w: 50, h: 30 });
    const [cx, cy] = centre(r);
    assert.equal(cx < area.width / 2, left);
    assert.equal(cy < area.height / 2, top);
    assert.ok(r.x >= 0 && r.y >= 0 && r.x + r.width <= area.width && r.y + r.height <= area.height);
    assert.ok(!(tx + 50 > r.x && tx < r.x + r.width && ty + 30 > r.y && ty < r.y + r.height), "covers the target");
  }
});

test("source window: with no target it sits top right, clear of the card and bars at the bottom", () => {
  const r = L.cornerAway(area, size, undefined);
  assert.ok(r.x > area.width / 2 && r.y < area.height / 2);
});

test("source window: on a second display, stays on it", () => {
  const second = { x: 1706, y: 0, width: 1280, height: 720 };
  const r = L.cornerAway(second, size, { x: 1720, y: 20, w: 10, h: 10 });
  assert.ok(r.x >= second.x && r.x + r.width <= second.x + second.width);
});

test("source window: a place you left it stays on the screen", () => {
  assert.deepEqual(L.keepOnScreen({ x: 100, y: 100, width: 500, height: 400 }, area), { x: 100, y: 100, width: 500, height: 400 });
  assert.deepEqual(L.keepOnScreen({ x: 1600, y: 900, width: 500, height: 400 }, area), { x: 1206, y: 620, width: 500, height: 400 });
  assert.deepEqual(L.keepOnScreen({ x: -50, y: -50, width: 3000, height: 2000 }, area), { x: 0, y: 0, width: 1706, height: 1020 });
});

test("source window: only web links leave for the browser", () => {
  for (const good of ["https://youtu.be/a?t=9s", "http://example.com/x#:~:text=a%20b"]) assert.equal(L.isWebLink(good), true);
  for (const bad of ["file:///c:/x", "javascript:alert(1)", "ms-settings:", "https://a b", "", null, 7]) assert.equal(L.isWebLink(bad), false);
});

test("source window: its title is the one the engine leaves out", () => assert.ok(L.SOURCE_TITLE.startsWith("GhostGuide")));

const state = o => ({ type: "state", tutorial: "T", current: 3, of: 9, hidden: false, finished: false, titles: [], statuses: [], scheme: "dark", ...o });
const noop = () => {};
const actions = { hideResume: noop, next: noop, back: noop, source: noop, scheme: noop, importTutorial: noop, setKeyBar: noop, quit: noop };
const item = (menu, label) => menu.find(i => (i.label ?? "").startsWith(label));

test("tray: says where you are", () => {
  assert.equal(L.trayStatus({ engineUp: false }), "Waiting for the engine");
  assert.equal(L.trayStatus({ engineUp: true }), "No tutorial open");
  assert.equal(L.trayStatus({ engineUp: true, state: state({}) }), "Step 3 of 9");
  assert.equal(L.trayStatus({ engineUp: true, state: state({ hidden: true }) }), "Paused at step 3 of 9");
  assert.equal(L.trayStatus({ engineUp: true, state: state({ finished: true }) }), "T: finished");
});

test("tray: redraws only when something it shows has changed", () => {
  const v = o => ({ engineUp: true, keyBar: true, sourceOpen: false, state: state(o) });
  assert.equal(L.trayKey(v({ scheme: "dark", statuses: ["done"] })), L.trayKey(v({ scheme: "light", statuses: ["pending"] })));
  for (const o of [{ current: 4 }, { hidden: true }, { finished: true }]) assert.notEqual(L.trayKey(v(o)), L.trayKey(v({})));
  assert.notEqual(L.trayKey({ ...v({}), keyBar: false }), L.trayKey(v({})));
  assert.notEqual(L.trayKey({ ...v({}), sourceOpen: true }), L.trayKey(v({})));
});

test("tray: the menu matches what can be done now", () => {
  const nothing = L.trayMenu({ engineUp: false, keyBar: true, sourceOpen: false }, actions);
  assert.equal(item(nothing, "Next").enabled, false);
  assert.equal(item(nothing, "Open this").enabled, false);
  assert.notEqual(item(nothing, "Import").enabled, false);
  assert.notEqual(item(nothing, "Quit").enabled, false);

  const paused = L.trayMenu({ engineUp: true, state: state({ hidden: true }), keyBar: false, sourceOpen: false }, actions);
  assert.ok(item(paused, "Resume"));
  assert.equal(item(paused, "Next").enabled, false);
  assert.equal(item(paused, "Show the shortcuts").checked, false);

  const first = L.trayMenu({ engineUp: true, state: state({ current: 1 }), keyBar: true, sourceOpen: true }, actions);
  assert.ok(item(first, "Hide"));
  assert.equal(item(first, "Back").enabled, false);
  assert.ok(item(first, "Close the source"));
  for (const i of first) if (i.accelerator) assert.equal(i.registerAccelerator, false, "the global keys already do this");
});
