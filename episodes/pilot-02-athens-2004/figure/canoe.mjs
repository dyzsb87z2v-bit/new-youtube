// Isometric figure of an Olympic white-water canoe slalom course, built with the anatomy kit.
// pageFor({ water, flow, gates, weeds, crane, ... }) returns a standalone page for one frame:
//   water  0..1  water level in the channel (1 = full, 0 = drained)
//   flow   world units the surface pattern has travelled (animates the current)
//   gates  0..1  how much of the slalom gate line is still hanging
//   weeds  0..1  how overgrown the dry channel and stand are
//   crane  0..1  a tower crane rising behind the course (redevelopment)
// World units are about 1 m x 4. x runs downstream, y across, z up.
import * as k from "../../../.agents/skills/anatomy/kit/iso-kit.mjs";
import * as G from "../../../.agents/skills/anatomy/kit/lathe.mjs";

const WIDTH = 600, HEIGHT = 560;
const X0 = -86, X1 = 86;
const WALL = { y: 13, t: 3, h: 11 };
const P = k.fitProjection(
  [[-96, -66, -5], [96, 62, -5], [-96, 62, 0], [96, -66, 0], [-78, -58, 96], [40, -58, 96]],
  WIDTH, HEIGHT, { pad: 22, azimuth: 40 },
);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (pts, style) => k.dotsSvg(pts, style);
const slab = (x0, x1, y0, y1, z, h, r = 1, steps = 3, bevel = 0.4) => k.slabOf({ x: x0, y: y0, w: x1 - x0, d: y1 - y0, r }, z, h, P, steps, bevel);

// deterministic pseudo-random for weeds
const rnd = (i) => { const s = Math.sin(i * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };

function ground() {
  const plan = { x: -96, y: -66, w: 192, d: 128, r: 3 };
  const out = [`<path class="iso-halo" d="${k.haloOf(plan, -5, 5, P)}"/>`];
  out.push(S(k.slabOf(plan, -5, 5, P, 4, 0.8), { tone: "lo" }));
  const joints = [];
  for (let x = -72; x <= 72; x += 24) joints.push(k.lineOnTop([x, 24], [x, 62], 0, P));
  joints.push(k.lineOnTop([-96, 24], [96, 24], 0, P));
  out.push(L(joints.join(""), { tone: "faint" }));
  // survey strip along the near edge, with a tick every 4 units (one metre)
  const strip = { x: -90, y: 54, w: 180, d: 6, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.8, P, 3), { tone: "lo", crease: "none" }));
  const ticks = k.topTicks(strip.x + 2, strip.x + strip.w - 2, 4, 5, strip.y + 0.8, 0.8, [2, 3.6], P);
  out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
  return out.join("");
}

function crane(rise) {
  if (rise <= 0.001) return "";
  const out = [];
  const x = -70, y = -54, top = 18 + 74 * rise;
  out.push(S(slab(x - 6, x + 6, y - 6, y + 6, 0, 3, 1), { tone: "mid" }));
  out.push(S(slab(x - 2.4, x + 2.4, y - 2.4, y + 2.4, 3, top - 3, 0.4, 2, 0), { tone: "mid", crease: "none" }));
  // lattice bracing on the two visible faces
  const lat = [];
  for (let z = 6; z < top - 4; z += 7) {
    lat.push(k.segment([x + 2.4, y - 2.4, z], [x + 2.4, y + 2.4, z + 7], P));
    lat.push(k.segment([x - 2.4, y + 2.4, z], [x + 2.4, y + 2.4, z + 7], P));
  }
  out.push(L(lat.join(""), { tone: "lo" }));
  if (rise > 0.95) {
    const a = (rise - 0.95) / 0.05;
    out.push(`<g opacity="${a.toFixed(2)}">`);
    out.push(S(slab(x - 14, x + 62, y - 1.4, y + 1.4, top, 2.8, 0.4, 2, 0), { tone: "mid" }));          // jib
    out.push(S(slab(x - 18, x - 8, y - 3, y + 3, top - 2, 4, 0.6), { tone: "lo" }));                // counterweight
    out.push(S(slab(x - 2.6, x + 2.6, y - 2.6, y + 2.6, top + 2.8, 5, 0.6), { tone: "mid" }));      // cab/apex
    out.push(k.wireSvg(at([x + 48, y, top]), at([x + 48, y, top - 30]), { tone: "lo", size: 0.9 }));
    out.push(`</g>`);
  }
  return out.join("");
}

function stand(weeds) {
  // five tiers of seating on the far bank
  const out = [];
  for (let i = 4; i >= 0; i--) {
    const y0 = -WALL.y - WALL.t - 6 - 5 * (i + 1), y1 = y0 + 5;
    out.push(S(slab(-60, 50, y0, y1, 0, 3 + 3 * i, 0.6, 2, 0.4), { tone: "mid" }));
    const seats = [];
    for (let x = -56; x <= 46; x += 4) seats.push(at([x, y0 + 2.5, 3 + 3 * i]));
    out.push(D(seats, { size: 0.5, tone: "lo" }));
  }
  out.push(L([k.lineOnTop([-60, -WALL.y - WALL.t - 6], [50, -WALL.y - WALL.t - 6], 0, P)].join(""), { tone: "faint" }));
  if (weeds > 0) out.push(weedDots(-58, 48, -WALL.y - WALL.t - 30, -WALL.y - WALL.t - 7, 3, weeds, 40, 900));
  return out.join("");
}

function pumpHouse() {
  const out = [];
  const x0 = -96 + 4, x1 = X0 - 2;
  out.push(S(slab(x0, x1 + 4, -24, 24, 0, 22, 1.4, 3, 0.6), { tone: "mid" }));
  out.push(L(k.planOutline({ x: x0 + 3, y: -21, w: x1 + 4 - x0 - 6, d: 42, r: 1 }, 22, P), { tone: "faint" }));
  // louvres on the downstream face
  const lv = [];
  for (let z = 6; z <= 16; z += 2.5) lv.push(k.segment([x1 + 4, -16, z], [x1 + 4, -6, z], P));
  out.push(L(lv.join(""), { tone: "lo" }));
  out.push(D([[x0 + 2, -22], [x0 + 2, 22], [x1 + 2, -22], [x1 + 2, 22]].map(([x, y]) => at([x, y, 22])), { size: 0.45 }));
  // intake pipe from the sea side, a flanged round pipe along y
  const F = G.frameOf([x0 + 14, 24, 8], [0, 1, 0], [1, 0, 0], [0, 0, 1]);
  out.push(S(G.disc(0, 18, 4, F, P), { tone: "mid", crease: "none" }));
  out.push(S(G.disc(-0.2, 1.6, 5.6, F, P), { tone: "mid" }));
  out.push(S(G.disc(16, 18, 5.6, F, P), { tone: "mid" }));
  out.push(D(G.dotsOf(F, 18, 4.8, 8, P, { all: true }), { size: 0.4, tone: "lo" }));
  return out.join("");
}

function wallFar() {
  return S(slab(X0, X1, -WALL.y - WALL.t, -WALL.y, 0, WALL.h, 0.6, 2, 0.5), { tone: "mid" });
}
function wallNear() {
  const out = [S(slab(X0, X1, WALL.y, WALL.y + WALL.t, 0, WALL.h, 0.6, 2, 0.5), { tone: "mid" })];
  const seams = [];
  for (let x = X0 + 16; x < X1; x += 16) seams.push(k.segment([x, WALL.y + WALL.t, 0.6], [x, WALL.y + WALL.t, WALL.h - 0.6], P));
  out.push(L(seams.join(""), { tone: "faint" }));
  return out.join("");
}

const OBSTACLES = [[-58, -1, 7], [-40, 1, 5.5], [-20, -1, 7.5], [2, 1, 6], [24, -1, 7], [46, 1, 5.5], [66, -1, 6.5]];
function channelFloor(weeds) {
  const out = [S(slab(X0, X1, -WALL.y, WALL.y, 0, 1, 0.4, 2, 0), { tone: "lo", crease: "none" })];
  // concrete obstacles that make the white water, alternating banks
  for (const [x, side, h] of OBSTACLES) {
    const y0 = side < 0 ? -WALL.y : WALL.y - 7;
    out.push(S(slab(x - 4, x + 4, y0, y0 + 7, 1, h, 1, 3, 0.4), { tone: "mid" }));
  }
  if (weeds > 0) out.push(weedDots(X0 + 4, X1 - 4, -WALL.y + 1, WALL.y - 1, 1, weeds, 70, 100));
  return out.join("");
}

function water(level, flow) {
  if (level <= 0.01) return "";
  const z = 1 + 8.5 * level;
  const poly = [[X0, -WALL.y], [X1, -WALL.y], [X1, WALL.y], [X0, WALL.y]].map(([x, y]) => at([x, y, z]));
  const d = "M" + poly.map((p) => p.join(" ")).join("L") + "Z";
  const out = [`<path d="${d}" fill="#3f7fa6" fill-opacity="${(0.35 + 0.25 * level).toFixed(2)}" stroke="none"/>`];
  // current lines that travel downstream, broken by the obstacles
  const lines = [];
  for (let row = 0; row < 7; row++) {
    const y = -WALL.y + 2 + row * 3.6;
    const off = ((flow * (1 + 0.15 * row)) % 22 + 22) % 22;
    for (let x = X0 + off; x < X1 - 6; x += 22) {
      const len = 6 + 4 * rnd(row * 7 + Math.floor(x));
      lines.push(k.lineOnTop([x, y], [Math.min(x + len, X1 - 1), y + 0.6 * Math.sin(x * 0.2)], z, P));
    }
  }
  out.push(`<g opacity="${(0.4 + 0.6 * level).toFixed(2)}">${L(lines.join(""), { tone: "hi" })}</g>`);
  // foam where water piles against each obstacle
  out.push(D(OBSTACLES.flatMap(([x, side]) => [0, 1, 2].map((i) => at([x - 5 - i * 1.6, (side < 0 ? -WALL.y + 3 : WALL.y - 3) + (i - 1) * 1.5, z]))), { size: 0.7, tone: "hi" }));
  return out.join("");
}

function gates(amount) {
  if (amount <= 0.01) return "";
  const out = [];
  const zTop = 32;
  for (const x of [-48, -6, 36]) {
    // two posts on the banks and a span wire, with hanging poles
    for (const y of [-WALL.y - 1.5, WALL.y + 1.5]) out.push(S(k.cylinder(x, y, 0.9, WALL.h, zTop - WALL.h, P, 12), { tone: "mid", crease: "none" }));
    out.push(L(k.segment([x, -WALL.y - 1.5, zTop], [x, WALL.y + 1.5, zTop], P), { tone: "lo" }));
    const poles = [];
    for (const y of [-4, 4]) {
      const bottom = 13 + (1 - amount) * 16;
      poles.push(k.segment([x, y, zTop], [x, y, bottom], P));
    }
    out.push(`<g opacity="${amount.toFixed(2)}">${L(poles.join(""), { tone: "lit" })}${D([at([x, -4, 13 + (1 - amount) * 16]), at([x, 4, 13 + (1 - amount) * 16])], { size: 0.7, tone: "hi" })}</g>`);
  }
  return out.join("");
}

function weedDots(x0, x1, y0, y1, z, amount, count, seed) {
  const pts = [];
  const n = Math.round(count * amount);
  for (let i = 0; i < n; i++) {
    const x = x0 + (x1 - x0) * rnd(seed + i), y = y0 + (y1 - y0) * rnd(seed + i + 500);
    pts.push(at([x, y, z]));
    pts.push(at([x + 0.6, y - 0.4, z + 1.2]));
  }
  return D(pts, { size: 0.55, tone: "mid" });
}

export const CSS_TINT = `
.iso[data-theme="dark"], body.iso { --anatomy-page:#172029; --anatomy-card:#1b2530; --anatomy-paper:#1b2530; --anatomy-face:#22303d; --anatomy-top:#243241;
 --anatomy-shade-0:#16202a; --anatomy-shade-1:#19242f; --anatomy-shade-2:#1c2834; --anatomy-shade-3:#202d3a;
 --anatomy-lit-top:#3a3424; --anatomy-lit-shade:#2c281d; --anatomy-hi:#e6ecef; --anatomy-mid:#7f909e; --anatomy-lo:#46576a; --anatomy-faint:#2d3b4b;
 --anatomy-lit:#f2c94c; --anatomy-dot:#e6ecef; --anatomy-halo:#0b1117; }
.iso-plate-corner, .iso-face-text { font-family: "Archivo", sans-serif !important; letter-spacing: 0 !important; text-transform: none !important; }
`;

export function figureSvg({ water: level = 1, flow = 0, gates: g = 1, weeds = 0, crane: c = 0 } = {}) {
  const body = [ground(), crane(c), stand(weeds), pumpHouse(), wallFar(), channelFloor(weeds), water(level, flow), gates(g), wallNear()];
  return k.figureSvg({
    width: WIDTH, height: HEIGHT,
    label: "An Olympic white-water canoe slalom course: a concrete channel with obstacles, a pump house at the top, a seating stand on the far bank and slalom gates hanging on wires. The figure shows the channel full of moving water, then drained, overgrown and overlooked by a construction crane.",
    body,
  });
}

export function pageFor(opts, fontDir) {
  const faces = fontDir ? `@font-face{font-family:"Archivo";font-weight:500;src:url("file://${fontDir}/Archivo-Medium.ttf")}@font-face{font-family:"Archivo";font-weight:600;src:url("file://${fontDir}/Archivo-SemiBold.ttf")}` : "";
  const plate = k.plateHtml({ fig: opts.fig || "Fig 2", title: opts.title || "", hint: opts.hint || "", readout: opts.readout || "", body: `<div class="iso-stage">${figureSvg(opts)}</div>` });
  const html = k.pageHtml({ title: "Canoe slalom course", theme: "dark", body: plate, width: 620 });
  return html.replace("</style>", `${faces}${CSS_TINT} .iso-page{margin:0 auto!important;padding:10px 0} body{background:#172029!important}</style>`);
}
