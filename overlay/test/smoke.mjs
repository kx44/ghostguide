// Renderer smoke test, no Electron needed: loads out/renderer in Chromium (Playwright) with a fake
// window.ghost bridge, draws every style in both schemes on a fake app, and checks the result.
// Screenshots go to out/smoke/. Run: npm run smoke   (cloud has Playwright; locally optional)
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const here = dirname(fileURLToPath(import.meta.url));
const page_url = pathToFileURL(join(here, "..", "out", "renderer", "index.html")).href;
const shots = join(here, "..", "out", "smoke");
mkdirSync(shots, { recursive: true });

const W = 1280, H = 800;
const step = (n, title) => ({ n, of: 23, title, source_t: "01:39" });
const card = (title, extra = {}) => ({ meta: `Step 2 of 23 · Visual Studio Code`, title, why: "Start the page.", done_when: "index.html open in editor",
  actions: ["show_me", "next"], ...extra });
const box = { x: 200, y: 120, w: 140, h: 24 };
const CASES = [
  ["outline", { style: "outline", box, extra: { action: "click", label: "New File" }, card: card("New file") }, [".outline", ".card"]],
  ["ghost_line", { style: "ghost_line", line: { from: [420, 420], to: [700, 420] }, extra: { action: "draw_line", pill: "50 mm" }, card: card("Draw a 50 mm line") }, ["svg line", ".pill", ".card"]],
  ["beacon", { style: "beacon", box, extra: { action: "click", label: "index.html" } }, [".beacon"]],
  ["static_line", { style: "static_line", line: { from: [420, 420], to: [600, 300] }, extra: { pill: "6 mm" } }, ["svg line", ".pill"]],
  ["ghost_text", { style: "ghost_text", box: { x: 80, y: 160, w: 220, h: 22 }, extra: { action: "type", value: "index.html", then_key: "Enter" },
    card: card("Name it index.html", { detail: "Type “index.html”, then press Enter.", actions: ["show_me", "next"] }) }, [".ghosttxt", ".outline", ".card", ".pill .kc"]],
  ["ghost_text_code", { style: "ghost_text", box: { x: 380, y: 300, w: 520, h: 20 },
    extra: { action: "type", value: '<div class="videos">\n  <section class="video-section">\n    <article class="video-container">\n    </article>\n  </section>\n</div>\n', multiline: true },
    card: card("Videos wrapper, section and card", { detail: "Type the faint code in Editor." }) }, [".ghosttxt.code", ".card"]],
  ["keycaps", { style: "keycaps", box: { x: 62, y: 4, w: 34, h: 24 }, extra: { action: "shortcut", keys: ["Ctrl", "S"] }, card: card("Save", { detail: "Press Ctrl + S.", actions: ["next"] }) }, [".card .keys .kc", ".outline.dash"]],
  ["mask", { style: "mask", box: { x: 600, y: 250, w: 90, h: 70 }, extra: { action: "pick", label: "Flat face inside the head" }, card: card("Select the face") }, ["svg ellipse", ".pill", ".card"]],
  ["path_chips", { style: "path_chips", box: { x: 70, y: 134, w: 220, h: 22 }, extra: { action: "menu_path", path: ["index.html (right-click)", "Open with Live Server"], path_done: 0,
    shortcut: "Alt+L Alt+O", click_type: { button: "right", count: 1, modifiers: [], label: "Right-click" } },
    card: card("Open with Live Server", { low_confidence: true }) }, [".card .chips .chip.cur", ".outline", "svg rect"]],
  ["offscreen", { style: "offscreen", box: { x: 2500, y: 300, w: 20, h: 20 }, extra: { label: "Revolve", direction: "right", edge_point: [W - 28, 310] },
    card: card("Bring Revolve into view", { actions: ["next"] }) }, [".edge", ".card"]],
  ["taskbar", { style: "taskbar", box: { x: 600, y: H - 44, w: 40, h: 40 }, extra: { action: "switch_app", app: "Chrome" }, card: card("Switch to Chrome") }, [".outline", ".card .alt .kc"]],
  ["click_type", { style: "click_type", box: { x: 20, y: 300, w: 120, h: 20 }, extra: { action: "click", click_type: { button: "left", count: 2, modifiers: [], label: "Double-click" } },
    card: card("Double-click Front Plane") }, [".outline", ".pill", "svg rect"]],
  ["signal_card", { style: "signal_card", box: { x: 660, y: 100, w: 600, h: 600 }, extra: { action: "wait", signals: ["new tab", "page loaded"] },
    card: card("Wait for the page", { actions: ["skip_wait"] }) }, [".card .sig", ".card .bar"]],
  ["card", { style: "card", extra: { action: "menu_path", path: ["Insert", "Cut", "Extrude"], keys: [] }, card: card("Look at the cut", { actions: ["next"], suggested: "width 5mm" }) }, [".card .chips", ".card .sug"]],
];
const STATE = (hidden = false) => ({ type: "state", tutorial: "YouTube clone", current: 2, of: 23, hidden, finished: false,
  titles: Array.from({ length: 23 }, (_, i) => `Step title ${i + 1}`), statuses: ["done", ...Array(22).fill("pending")], scheme: "dark" });

const fakeApp = scheme => `
  html { background: ${scheme === "light" ? "#f3f3f3" : "#1e1e1e"} !important; }
  body:before { content:""; position:fixed; left:0; top:0; width:300px; height:100%; background:${scheme === "light" ? "#e4e4e4" : "#252526"}; }
  body:after { content:""; position:fixed; left:0; right:0; bottom:0; height:44px; background:${scheme === "light" ? "#eceef2" : "#202020"}; }`;

const browser = await chromium.launch();
const errors = [];
let failures = 0;
for (const scheme of ["light", "dark"]) {
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.on("pageerror", e => errors.push(`${scheme}: ${e.message}`));
  page.on("console", m => { if (m.type() === "error") errors.push(`${scheme} console: ${m.text()}`); });
  await page.addInitScript(() => {
    window.__sent = [];
    window.ghost = { on(cb) { window.__push = cb; }, send(m) { window.__sent.push(m); }, setHitRects() {}, copy() {} };
  });
  await page.goto(page_url);
  await page.addStyleTag({ content: fakeApp(scheme) });
  const push = (msg, local = {}) => page.evaluate(([msg, local]) => window.__push({ msg, local, primary: true, display: { w: 1280, h: 800 } }), [msg, local]);
  await push(STATE());
  for (const [name, g, expect] of CASES) {
    const msg = { type: "guide", step: step(2, "x"), scheme, extra: {}, ...g };
    const local = { box: g.box, line: g.line, edge_point: g.extra?.edge_point };
    await push(msg, local);
    await page.waitForTimeout(name.includes("line") ? 900 : 350);
    for (const sel of expect) {
      if (!(await page.$(`#guide ${sel}`))) { failures++; console.log(`FAIL ${scheme}/${name}: missing ${sel}`); }
    }
    const c = await page.$("#guide .card");
    if (c) {
      const b = await c.boundingBox();
      if (b.x < 0 || b.y < 0 || b.x + b.width > W || b.y + b.height > H) { failures++; console.log(`FAIL ${scheme}/${name}: card off-window`, b); }
      if (g.box && g.style !== "signal_card" && g.style !== "offscreen") {
        const o = { x: g.box.x - 4, y: g.box.y - 4, r: g.box.x + g.box.w + 4, btm: g.box.y + g.box.h + 4 };
        if (b.x < o.r && b.x + b.width > o.x && b.y < o.btm && b.y + b.height > o.y) { failures++; console.log(`FAIL ${scheme}/${name}: card covers the target`); }
      }
    }
    await page.screenshot({ path: join(shots, `${scheme}-${name}.png`) });
  }
  // Show me, card buttons, mark, toast, step rail, hide
  await push({ type: "guide", step: step(1, "New file"), scheme, style: "outline", box, extra: {}, card: card("New file") }, { box });
  await page.click("#guide .card button[data-a=show_me]");
  await push({ type: "show_me", to: [270, 132], click: "left" }, { to: [270, 132] });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: join(shots, `${scheme}-show_me.png`) });
  await push({ type: "mark", result: "ok" });
  if (!(await page.$("#guide .outline.ok"))) { failures++; console.log(`FAIL ${scheme}: mark ok`); }
  await push({ type: "toast", text: "✓ Caught up: steps 2–5 done. You're on step 6.", kind: "ok", ms: 3000 });
  await page.click("#shell .bar-ctl button[data-a=rail]");
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(shots, `${scheme}-rail-toast.png`) });
  await page.click("#shell .rail .row[data-n='5']");
  await page.click("#shell .bar-ctl button[data-a=skip]");
  await push(STATE(true));
  await push({ type: "clear", reason: "hidden" });
  if (await page.$("#guide .outline")) { failures++; console.log(`FAIL ${scheme}: clear left guidance`); }
  await page.screenshot({ path: join(shots, `${scheme}-hidden.png`) });
  const sent = await page.evaluate(() => window.__sent.map(m => m.type + (m.n ? m.n : "")));
  if (sent.join(",") !== "show_me,jump5,skip") { failures++; console.log(`FAIL ${scheme}: sent ${sent}`); }
  await page.close();
}
await browser.close();
for (const e of errors) console.log("ERROR", e);
const total = failures + errors.length;
console.log(total ? `smoke: ${total} problem(s)` : `smoke: ok, ${CASES.length} styles × 2 schemes, screenshots in ${shots}`);
process.exit(total ? 1 : 0);
