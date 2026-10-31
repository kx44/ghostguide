// Bundles main + preload (Node, CommonJS) and the renderer (browser, IIFE) into out/. Type-check: npm run typecheck.
import { build } from "esbuild";
import { cpSync, mkdirSync } from "node:fs";

const common = { bundle: true, sourcemap: true, target: "es2022", logLevel: "warning" };
await Promise.all([
  build({ ...common, entryPoints: ["main/main.ts", "main/preload.ts", "main/importPreload.ts", "main/sourcePreload.ts"], outdir: "out/main", platform: "node",
          format: "cjs", external: ["electron", "bufferutil", "utf-8-validate"] }),
  build({ ...common, entryPoints: ["renderer/app.ts"], outdir: "out/renderer", platform: "browser", format: "iife" }),
  build({ ...common, entryPoints: ["renderer/shell/importScreen.ts", "renderer/shell/sourceView.ts"], outdir: "out/renderer", platform: "browser", format: "iife" }),
]);
mkdirSync("out/renderer", { recursive: true });
cpSync("renderer/index.html", "out/renderer/index.html");
cpSync("renderer/import.html", "out/renderer/import.html");
cpSync("renderer/source.html", "out/renderer/source.html");
cpSync("renderer/styles", "out/renderer/styles", { recursive: true });
cpSync("assets", "out/assets", { recursive: true });
console.log("built out/");
