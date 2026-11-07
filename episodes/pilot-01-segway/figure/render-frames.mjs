// Renders the Segway figure as a PNG frame sequence for one 10-second video slot.
//   node render-frames.mjs <slot1|slot2> <outDir>
// Each frame is the anatomy card (.iso-plate) captured at 2x in headless Chromium.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { pageFor } from "./segway.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const [, , slot, outDir] = process.argv;
const FPS = 30, N = 300;
const fonts = new URL("../edit/fonts", import.meta.url).pathname;
const ease = (x) => { x = Math.max(0, Math.min(1, x)); return x * x * (3 - 2 * x); };

// Simple, honest motion model: wheel speed follows lean (the machine drives
// under the rider to stay upright). Units are illustrative, so the readout
// shows the lean angle, not an invented speed.
function slot1(t) {
  const lean = 5.5 * ease((t - 1.2) / 2.5) + 0.6 * Math.sin(t * 2.4) * ease((t - 3.5) / 1.5);
  return { lean, power: 1, title: "Code name: Ginger", hint: "Tilt sensors check balance more than 100 times a second",
    readout: lean < 0.3 ? "standing level" : `lean +${lean.toFixed(1)}°, wheels roll forward` };
}
function slot2(t) {
  const lean = 4.5 * (1 - ease((t - 0.5) / 3.5));
  const power = t < 6.2 ? 1 : 0;
  return { lean, power, title: "Segway PT, 2001 to 2020", hint: "Production of the original ended on 15 July 2020",
    readout: power ? (lean < 0.3 ? "standing level" : `lean +${lean.toFixed(1)}°, slowing down`) : "switched off" };
}

const model = slot === "slot2" ? slot2 : slot1;
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 640, height: 760 }, deviceScaleFactor: 2 });
let travel = 0;
for (let i = 0; i < N; i++) {
  const t = i / FPS;
  const m = model(t);
  travel += m.lean * 2.2 / FPS * 10;            // wheel advance proportional to lean
  await page.setContent(pageFor({ ...m, travel }, fonts), { waitUntil: "load" });
  if (i === 0) await page.evaluate(() => document.fonts.ready);
  await page.locator(".iso-plate").screenshot({ path: `${outDir}/f${String(i).padStart(4, "0")}.png`, animations: "disabled" });
  if (i % 60 === 0) console.log(slot, i);
}
await browser.close();
