// Isometric cutaway of a Segway PT, built with the anatomy kit.
// figureHtml({ lean, travel, power }) returns a standalone page for one frame:
//   lean   chassis pitch in degrees about the axle (+ = forward)
//   travel distance rolled in world units (turns the wheels, scrolls the pavement)
//   power  0..1, dims the lit balance sensors when the machine is switched off
//
// World units are about 1 cm. x points forward, y across the axle, z up.
// Facts used (see ../sources.csv): self-balancing, two wheels, tilt sensors that
// check the rider's balance more than 100 times a second (ABC News, 2001).
import * as k from "../../../.agents/skills/anatomy/kit/iso-kit.mjs";
import * as G from "../../../.agents/skills/anatomy/kit/lathe.mjs";

const WIDTH = 600, HEIGHT = 560;
const AXLE_Z = 24, WHEEL_R = 24, RIM_R = 15.5, TIRE_W = 9;
const TRACK = 35;                       // wheel centre plane, |y|
const TRAY = { x0: -23, x1: 23, y0: -26, y1: 26, z0: 7, z1: 20 };
const COLUMN = { x: 16.5, y: 0, z0: 18, z1: 104, r: 2.6 };
const BAR_Z = 104, BAR_HALF = 27;

const P = k.fitProjection(
  [[-58, -50, -6], [58, 50, -6], [-58, 50, 0], [58, -50, 0], [COLUMN.x + 10, -BAR_HALF - 3, BAR_Z + 6], [COLUMN.x + 10, BAR_HALF + 3, BAR_Z + 6]],
  WIDTH, HEIGHT, { pad: 26, azimuth: 48 },
);
const at = (p) => k.iso(p, P);
const S = (paths, style) => k.solidSvg(paths, style);
const L = (d, style) => k.lineSvg(d, style);
const D = (pts, style) => k.dotsSvg(pts, style);

// ---------- chassis frame (rotates about the axle with lean) ----------
function chassis(leanDeg) {
  const t = (leanDeg * Math.PI) / 180, c = Math.cos(t), s = Math.sin(t);
  const ex = [c, 0, -s], ey = [0, 1, 0], ez = [s, 0, c];
  const R = ([x, y, z]) => { const dz = z - AXLE_Z; return [x * c + dz * s, y, AXLE_Z - x * s + dz * c]; };
  const frameZ = (z0) => G.frameOf(R([0, 0, z0]), ez, ex, ey);           // prisms standing on the chassis floor
  const frameY = (x, z) => G.frameOf(R([x, 0, z]), ey, ex, ez);          // round parts across the axle
  const frameUp = (x, y, z) => G.frameOf(R([x, y, z]), ez, ex, ey);      // round parts standing up
  return { R, frameZ, frameY, frameUp, ex, ey, ez };
}

const rounded = (x0, x1, y0, y1, r, steps = 4) => {
  const out = [];
  const cs = [[x1 - r, y1 - r, 0], [x0 + r, y1 - r, Math.PI / 2], [x0 + r, y0 + r, Math.PI], [x1 - r, y0 + r, 1.5 * Math.PI]];
  for (const [cx, cy, a0] of cs) for (let i = 0; i <= steps; i++) {
    const a = a0 + (i / steps) * (Math.PI / 2);
    out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return out;
};
const box = (C, x0, x1, y0, y1, z0, z1, r = 1) => G.prismOf(C.frameZ(z0), rounded(x0, x1, y0, y1, r), 0, z1 - z0, P);

// ---------- ground: a strip of pavement that scrolls under the wheels ----------
function ground(travel) {
  const slab = { x: -58, y: -50, w: 116, d: 100, r: 3 };
  const out = [`<path class="iso-halo" d="${k.haloOf(slab, -6, 6, P)}"/>`];
  out.push(S(k.slabOf(slab, -6, 6, P, 4, 0.8), { tone: "lo" }));
  // paving joints every 28 units, scrolling backwards as the machine rolls forward
  const joints = [];
  const off = ((-travel % 28) + 28) % 28;
  for (let x = -58 + off; x < 58; x += 28) if (x > -56 && x < 56) joints.push(k.lineOnTop([x, -50], [x, 50], 0, P));
  joints.push(k.lineOnTop([-58, 0.5], [58, 0.5], 0, P));
  out.push(L(joints.join(""), { tone: "faint" }));
  // kerb strip with distance ticks along the near edge
  const strip = { x: -54, y: 41, w: 108, d: 6, r: 1 };
  out.push(S(k.slabOf(strip, 0, 0.8, P, 3), { tone: "lo", crease: "none" }));
  const minor = [], major = [];
  const toff = ((-travel % 5) + 5) % 5;
  for (let x = strip.x + 2 + toff, i = 0; x < strip.x + strip.w - 2; x += 5, i++) {
    const idx = Math.round((x - toff + travel) / 5);
    const isMajor = ((idx % 5) + 5) % 5 === 0;
    (isMajor ? major : minor).push(k.lineOnTop([x, strip.y + 0.8], [x, strip.y + 0.8 + (isMajor ? 3.6 : 2)], 0.8, P));
  }
  out.push(L(minor.join(""), { tone: "lo" }), L(major.join(""), { tone: "mid" }));
  out.push(D([at([strip.x + 1.5, strip.y + 3, 0.8]), at([strip.x + strip.w - 1.5, strip.y + 3, 0.8])], { size: 0.45 }));
  return out.join("");
}

// ---------- a wheel (fixed axle position, spins with travel) ----------
function wheel(side, travel) {
  const y = side * TRACK;
  const F = G.frameOf([0, y, AXLE_Z], [0, side, 0], [1, 0, 0], [0, 0, 1]);   // axis points outward
  const spin = -travel / WHEEL_R * side;
  const out = [];
  const h = TIRE_W / 2;
  // tyre with a rounded shoulder
  out.push(S(G.lathe([[-h, RIM_R], [-h, WHEEL_R - 2.2], [-h + 0.9, WHEEL_R - 0.6, 1], [-h + 2.4, WHEEL_R, 1], [h - 2.4, WHEEL_R, 1], [h - 0.9, WHEEL_R - 0.6, 1], [h, WHEEL_R - 2.2], [h, RIM_R]], F, P, { hole: [h, RIM_R - 0.1] }), { tone: "lo", crease: "none" }));
  const tread = G.ribsOf(F, -h + 2.6, h - 2.6, WHEEL_R + 0.02, 54, P, { phase: spin, fade: [0.05, 0.4] });
  out.push(k.fadedSvg(tread, { tone: "faint" }));
  // rim, dished
  out.push(S(G.lathe([[h - 0.4, RIM_R + 0.2], [h + 0.3, RIM_R - 1], [h + 0.3, 6.5], [h + 1.2, 5.2], [h + 1.2, 0]], F, P), { tone: "mid" }));
  out.push(L(G.arcOf(F, h + 0.3, RIM_R - 3, P, { least: -1 }), { tone: "lo" }));
  out.push(L(G.spokesOf(F, h + 0.3, 6.8, RIM_R - 3.2, 5, P, { phase: spin, sweep: 0.18 }), { tone: "lo" }));
  out.push(D(G.dotsOf(F, h + 1.2, 3.2, 5, P, { phase: spin, all: true }), { size: 0.45, tone: "mid" }));
  out.push(S(G.disc(h + 1.2, h + 2.2, 2.2, F, P), { tone: "mid" }));
  // valve stem dot that visibly travels round
  out.push(D([k.iso(G.pointOf(F, h + 0.3, RIM_R - 1.6, spin + 0.7), P)], { size: 0.6, tone: "hi" }));
  return out.join("");
}

// ---------- chassis parts ----------
function motor(C, side) {
  const y0 = side * 26, F = G.frameOf(C.R([0, y0, AXLE_Z]), [0, side, 0], C.ex, C.ez);
  const out = [];
  out.push(S(G.solidOf([[0, 9.5], [4.2, 9.5], [5.2, 8.4], [5.2, 0]], F, P, { bevel: 0.5 }), { tone: "mid" }));
  out.push(L(G.arcOf(F, 2.1, 9.5, P), { tone: "faint" }));
  out.push(k.fadedSvg(G.ribsOf(F, 0.6, 3.6, 9.5, 28, P, { fade: [0.05, 0.4] }), { tone: "faint" }));
  out.push(D(G.dotsOf(F, 5.2, 6.6, 6, P, { all: true }), { size: 0.4, tone: "lo" }));
  return out.join("");
}

function tray(C, part) {
  const { x0, x1, y0, y1, z0, z1 } = TRAY;
  const out = [];
  if (part === "back") {
    out.push(S(box(C, x0, x1, y0, y1, z0, z0 + 2, 3), { tone: "lo" }));                  // floor pan
    out.push(S(box(C, x0, x0 + 2, y0, y1, z0 + 2, z1, 1), { tone: "mid" }));             // rear wall
    out.push(S(box(C, x0 + 2, x1, y0, y0 + 2, z0 + 2, z1, 1), { tone: "mid" }));         // far wall
    // rubber mat over the rear third, with grip ribs
    out.push(S(box(C, x0, -16, y0, y1, z1, z1 + 1.6, 2), { tone: "mid" }));
    const ribs = [];
    for (let y = y0 + 4; y <= y1 - 4; y += 3) ribs.push(k.segment(C.R([x0 + 3, y, z1 + 1.6]), C.R([-18.5, y, z1 + 1.6]), P));
    out.push(L(ribs.join(""), { tone: "lo" }));
    out.push(D([C.R([x0 + 1.4, y0 + 1.4, z1 + 1.6]), C.R([x0 + 1.4, y1 - 1.4, z1 + 1.6]), C.R([-17.4, y0 + 1.4, z1 + 1.6]), C.R([-17.4, y1 - 1.4, z1 + 1.6])].map(at), { size: 0.45 }));
  } else {
    out.push(S(box(C, x1 - 2, x1, y0, y1, z0 + 2, z0 + 7, 1), { tone: "mid" }));        // low front wall (cutaway)
    out.push(S(box(C, x0, x1 - 2, y1 - 2, y1, z0 + 2, z0 + 7, 1), { tone: "mid" }));     // low near wall (cutaway)
    out.push(L([k.segment(C.R([x1, y0 + 3, z0 + 7]), C.R([x1, y1 - 3, z0 + 7]), P)].join(""), { tone: "faint" }));
    out.push(D([C.R([x1, y0 + 4, z0 + 4.5]), C.R([x1, y1 - 4, z0 + 4.5])].map(at), { size: 0.45 }));
  }
  return out.join("");
}

function batteries(C) {
  const out = [];
  const b = { x0: -6, x1: 12, y0: 4, y1: 23, z0: 9, z1: 16.5 };
  out.push(S(box(C, b.x0, b.x1, b.y0, b.y1, b.z0, b.z1, 1.6), { tone: "mid" }));
  // cell seams across the top and a label plate
  const seams = [];
  for (let x = b.x0 + 5; x < b.x1 - 2; x += 5) seams.push(k.segment(C.R([x, b.y0 + 0.8, b.z1]), C.R([x, b.y1 - 0.8, b.z1]), P));
  out.push(L(seams.join(""), { tone: "faint" }));
  out.push(S(box(C, b.x0 + 3, b.x0 + 10, b.y0 + 3, b.y0 + 9, b.z1, b.z1 + 0.4, 0.6), { tone: "mid", crease: "none" }));
  // terminal posts
  for (const [x, y] of [[b.x1 - 3, b.y0 + 3], [b.x1 - 7, b.y0 + 3]]) out.push(S(G.disc(0, 1.4, 1.1, C.frameUp(x, y, b.z1), P), { tone: "mid" }));
  return out.join("");
}

function sensors(C, power) {
  const out = [];
  const b = { x0: -14, x1: 2, y0: -23, y1: -5, z0: 9, z1: 11 };
  out.push(S(box(C, b.x0, b.x1, b.y0, b.y1, b.z0, b.z1, 1), { tone: "hi", lit: power > 0.5 }));
  // mounting screws
  out.push(D([[b.x0 + 1.2, b.y0 + 1.2], [b.x1 - 1.2, b.y0 + 1.2], [b.x0 + 1.2, b.y1 - 1.2], [b.x1 - 1.2, b.y1 - 1.2]].map(([x, y]) => at(C.R([x, y, b.z1]))), { size: 0.45, tone: "mid" }));
  // gyro cans in a row and two tilt-sensor chips
  for (const [x, y] of [[-10.5, -19], [-6, -19], [-1.5, -19], [-10.5, -13.5], [-6, -13.5]]) {
    const F = C.frameUp(x, y, b.z1);
    out.push(S(G.disc(0, 2.6, 1.7, F, P), { tone: "hi", lit: power > 0.5 }));
    out.push(L(G.arcOf(F, 1.3, 1.7, P), { tone: "faint" }));
  }
  for (const [x, y] of [[-1.5, -13.5], [-1.5, -9]]) out.push(S(box(C, x - 1.6, x + 1.6, y - 1.6, y + 1.6, b.z1, b.z1 + 0.8, 0.3), { tone: "mid", crease: "none" }));
  // status LED
  out.push(D([at(C.R([b.x0 + 2.4, b.y1 - 2.4, b.z1]))], { size: 0.9, tone: power > 0.5 ? "hi" : "lo", pulse: power > 0.5 }));
  // harness to the battery terminals
  out.push(k.wireSvg(at(C.R([b.x0 + 3, b.y1 - 0.5, b.z1])), at(C.R([9, 6, 17.9])), { via: [at(C.R([b.x0 + 3, 1, 13]))], tone: "mid", size: 1 }));
  out.push(k.wireSvg(at(C.R([b.x1 - 1, b.y1 - 0.5, b.z1])), at(C.R([5, 6, 17.9])), { via: [at(C.R([b.x1 - 1, 0, 13.5]))], tone: "lo", size: 1 }));
  return out.join("");
}

function column(C) {
  const out = [];
  const { x, y, z0, z1, r } = COLUMN;
  out.push(S(box(C, x - 4, x + 4, y - 5, y + 5, z0 - 9, z0 + 1, 1.2), { tone: "mid" }));      // mount block
  out.push(D([[x - 2.6, y - 3.6], [x + 2.6, y - 3.6], [x - 2.6, y + 3.6], [x + 2.6, y + 3.6]].map(([a, b]) => at(C.R([a, b, z0 + 1]))), { size: 0.45 }));
  const F = C.frameUp(x, y, z0 + 1);
  out.push(S(G.disc(0, 3, r + 1.2, F, P), { tone: "mid" }));                                  // collar
  out.push(S(G.disc(3, z1 - z0 - 1, r, F, P), { tone: "mid", crease: "none" }));
  out.push(L([30, 60].map((s) => G.arcOf(F, s, r, P)).join(""), { tone: "faint" }));
  out.push(S(G.disc(42, 46, r + 0.7, F, P), { tone: "mid" }));                                 // clamp band
  out.push(D([k.iso(G.pointOf(F, 44, r + 0.7, G.angleToward(F, k.towardViewer(P).concat(0))), P)], { size: 0.5 }));
  return out.join("");
}

function handlebar(C) {
  const out = [];
  const top = BAR_Z, x = COLUMN.x;
  // head block where the bar meets the column
  out.push(S(box(C, x - 4.2, x + 4.2, -5.5, 5.5, top - 4, top + 3, 1.6), { tone: "mid" }));
  out.push(S(box(C, x - 2.2, x + 2.2, -3.2, 3.2, top + 3, top + 3.8, 0.8), { tone: "mid", crease: "none" }));  // info key dock
  out.push(D([at(C.R([x, 0, top + 3.8]))], { size: 0.7, tone: "hi" }));
  // bar across, then grips; far side first
  for (const side of [-1, 1]) {
    const F = G.frameOf(C.R([x, side * 5.5, top]), [0, side, 0], C.ex, C.ez);
    out.push(S(G.disc(0, BAR_HALF - 5.5 - 9, 1.5, F, P), { tone: "mid", crease: "none" }));
    out.push(S(G.solidOf([[BAR_HALF - 14.5, 2.2], [BAR_HALF - 5.5 - 0.6, 2.2], [BAR_HALF - 5.5, 1.8]], F, P), { tone: "lo" }));
    out.push(k.fadedSvg(G.ribsOf(F, BAR_HALF - 14, BAR_HALF - 6.6, 2.2, 20, P, { fade: [0.05, 0.4] }), { tone: "faint" }));
  }
  return out.join("");
}

// ---------- the page ----------
export const CSS_TINT = `
.iso[data-theme="dark"], body.iso { --anatomy-page:#172029; --anatomy-card:#1b2530; --anatomy-paper:#1b2530; --anatomy-face:#22303d; --anatomy-top:#243241;
 --anatomy-shade-0:#16202a; --anatomy-shade-1:#19242f; --anatomy-shade-2:#1c2834; --anatomy-shade-3:#202d3a;
 --anatomy-lit-top:#3a3424; --anatomy-lit-shade:#2c281d; --anatomy-hi:#e6ecef; --anatomy-mid:#7f909e; --anatomy-lo:#46576a; --anatomy-faint:#2d3b4b;
 --anatomy-lit:#f2c94c; --anatomy-dot:#e6ecef; --anatomy-halo:#0b1117; }
.iso-plate-corner, .iso-face-text { font-family: "Archivo", sans-serif !important; letter-spacing: 0 !important; text-transform: none !important; }
`;

export function figureSvg({ lean = 0, travel = 0, power = 1 } = {}) {
  const C = chassis(lean);
  const body = [
    ground(travel),
    wheel(-1, travel),
    motor(C, -1),
    tray(C, "back"),
    sensors(C, power),
    batteries(C),
    column(C),
    tray(C, "front"),
    handlebar(C),
    motor(C, 1),
    wheel(1, travel),
  ];
  return k.figureSvg({
    width: WIDTH, height: HEIGHT,
    label: "A Segway PT cut away: two wheels on one axle, a battery pack and a board of gyroscopes and tilt sensors in the tray between them, and a column up to the handlebar. When the column leans forward, the wheels roll forward to keep it upright.",
    body,
  });
}

export function plate({ lean = 0, travel = 0, power = 1, readout = "", title = "Segway PT, cut away", hint = "" } = {}) {
  return k.plateHtml({ fig: "Fig 1", title, hint, readout, body: `<div class="iso-stage">${figureSvg({ lean, travel, power })}</div>` });
}

export function pageFor(opts, fontDir) {
  const faces = fontDir ? `@font-face{font-family:"Archivo";font-weight:500;src:url("file://${fontDir}/Archivo-Medium.ttf")}@font-face{font-family:"Archivo";font-weight:600;src:url("file://${fontDir}/Archivo-SemiBold.ttf")}` : "";
  const html = k.pageHtml({ title: "Segway PT", theme: "dark", body: plate(opts), width: 620 });
  return html.replace("</style>", `${faces}${CSS_TINT} .iso-page{margin:0 auto!important;padding:10px 0} body{background:#172029!important}</style>`);
}
