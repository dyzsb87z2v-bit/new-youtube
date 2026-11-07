// Renders the canoe-course figure as a PNG frame sequence for one 10-second slot.
//   node render-frames.mjs <slot1|slot2> <outDir>
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { pageFor } from "./canoe.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const [, , slot, outDir] = process.argv;
const FPS = 30, N = 300;
const fonts = new URL("../../pilot-01-segway/edit/fonts", import.meta.url).pathname;
const ease = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };

function slot1(t) {
  return { water: ease(t / 1.5) * 0.9 + 0.1, flow: t * 9, gates: 1, weeds: 0, crane: 0,
    title: "Canoe slalom course, Athens 2004", hint: "Seawater from the bay, pumped through the channel",
    readout: t < 1.5 ? "filling" : "water running" };
}
function slot2(t) {
  const water = 1 - ease((t - 0.3) / 2.6), gates = 1 - ease((t - 1.5) / 2), weeds = ease((t - 3.5) / 3.5), crane = ease((t - 5.5) / 3.8);
  const readout = crane > 0.05 ? "2014: the whole site sold for redevelopment" : weeds > 0.05 ? "overgrown" : water > 0.02 ? "draining" : "drained";
  return { water, flow: t * 9 * water, gates, weeds, crane, title: "Same course, after the Games", hint: "Drained and left behind", readout };
}

const model = slot === "slot2" ? slot2 : slot1;
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 640, height: 760 }, deviceScaleFactor: 2 });
for (let i = 0; i < N; i++) {
  await page.setContent(pageFor(model(i / FPS), fonts), { waitUntil: "load" });
  if (i === 0) await page.evaluate(() => document.fonts.ready);
  await page.locator(".iso-plate").screenshot({ path: `${outDir}/f${String(i).padStart(4, "0")}.png`, animations: "disabled" });
}
await browser.close();
console.log("done", slot);
