#!/usr/bin/env python3
"""Build the 60-second cut of episode 02 (Athens 2004) for "So What Happened?".

Free tools only: Python + Pillow + numpy + FFmpeg, Node + headless Chromium for the
isometric figure (anatomy skill), Archivo (SIL OFL) for type.

Design system:
  graphite-blue base, paper text, steel secondary,
  hype yellow = what was promised / THEN, reality rust = what happened / NOW.
  Signature: a year ruler (2000-2026) whose marker moves from THEN to NOW.

Inputs:  images/*.jpg (licensed stills), vo/seg0..4.wav, fonts/*.ttf,
         ../figure/ (isometric Segway; frames are rendered on demand)
Outputs: out/so-what-happened-02-athens-2004.mp4, out/captions.srt
Usage:   python3 build.py
"""
import os, subprocess, wave, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, *a)
FIG = os.path.join(HERE, "..", "figure")
CACHE = os.environ.get("SWH_CACHE", os.path.join(HERE, "out", "frames"))
W, H, FPS, DUR = 1080, 1920, 30, 60.0
NF = int(FPS * DUR)

# ---------- tokens ----------
INK = (23, 32, 41)        # graphite blue, the page
PAPER = (230, 236, 239)   # text
STEEL = (127, 144, 158)   # secondary text, ticks
DEEP = (16, 23, 30)       # shadows, plate borders
HYPE = (242, 201, 76)     # what was promised
REAL = (200, 85, 61)      # what actually happened

FONTS = os.path.join(HERE, "..", "..", "pilot-01-segway", "edit", "fonts")   # shared channel fonts
def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, f"Archivo-{name}.ttf"), size)

F_HOOK = font("ExpandedBlack", 70)
F_DISPLAY = font("ExpandedBlack", 128)
F_DISPLAY_M = font("ExpandedExtraBold", 72)
F_CAP = font("SemiBold", 60)
F_BODY = font("Medium", 40)
F_SMALL = font("Medium", 26)
F_RULER = font("SemiBold", 26)
F_RULER_BIG = font("ExpandedExtraBold", 40)
F_END = font("ExpandedBlack", 104)

MARGIN = 60
CAP_Y = 1340            # caption block top; safe zone ends at 1600

# ---------- voiceover timing ----------
SEG_TEXT = [
    "In 2004, the world came to Athens for the Olympics. So what happened to the venues?",
    "Greece built a whole sports complex on its old airport, even a white-water canoe course. It was the first Olympic slalom ever run on seawater.",
    "The Games lasted seventeen days. Estimates put the bill at up to eleven billion euros. Ten years later, the softball stadium was a weed patch, the hockey pitch untouched, and the canoe course abandoned. A worker once told a reporter: it isn't abandoned, it's just that nobody ever plays softball. By then, Greece was deep in a debt crisis.",
    "In 2014, Greece agreed to hand the whole site to developers, in a deal worth nine hundred and fifteen million euros.",
    "Today, the old airport is becoming a new district called the Ellinikon. The Games took seventeen days. Reusing this site took twenty-two years.",
]
SEG_START = [0.0, 5.75, 15.2, 40.5, 50.0]
STING_AT = 58.7

def wav_dur(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()

SEG_DUR = [wav_dur(P("vo", f"seg{i}.wav")) for i in range(5)]

def caption_chunks():
    """Split each segment into short phrases timed by character count."""
    out = []
    for txt, st, du in zip(SEG_TEXT, SEG_START, SEG_DUR):
        words = txt.split()
        chunks, cur = [], []
        for w in words:
            cur.append(w)
            if len(cur) >= 5 or (w.endswith((".", "?", ":", ",")) and len(cur) >= 2):
                chunks.append(" ".join(cur)); cur = []
        if cur:
            chunks.append(" ".join(cur))
        total = sum(len(c) + 3 for c in chunks)
        t = st
        for c in chunks:
            d = du * (len(c) + 3) / total
            out.append((t, t + d, c))
            t += d
    return out

CAPS = caption_chunks()

def write_srt(path):
    def ts(x):
        ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    with open(path, "w") as f:
        for i, (a, b, c) in enumerate(CAPS, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{c}\n\n")

# ---------- helpers ----------
def ease(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)

def tw(d, s, f):
    b = d.textbbox((0, 0), s, font=f); return b[2] - b[0]

def wrap(d, s, f, maxw):
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if tw(d, t, f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def mix(c, a, bg=INK):
    return tuple(int(bg[i] + (c[i] - bg[i]) * a) for i in range(3))

def canvas():
    return Image.new("RGB", (W, H), INK)

# ---------- photo plates ----------
PLATE = (40, 420, 1000, 820)   # x, y, w, h of every photo plate
CROPS = {   # (centre x, centre y, zoom) as fractions of the source
    "A1": (0.30, 0.50, 1.00),
    "A2": (0.45, 0.55, 1.10),
    "A3": (0.50, 0.55, 1.00),
    "A4": (0.62, 0.62, 1.00),
    "A5": (0.50, 0.42, 1.00),
}
CREDITS = {
    "A1": "Opening ceremony, Athens, 13 August 2004. Photo: Alterego, CC BY-SA 3.0, Wikimedia Commons",
    "A2": "Hellinikon Olympic complex, 2019. Photo: Arne Müseler, CC BY-SA 3.0 DE, Wikimedia Commons",
    "A3": "Canoe slalom centre, 2019. Photo: Arne Müseler, CC BY-SA 3.0 DE, Wikimedia Commons",
    "A4": "Softball stadium, November 2018. Photo: Evanonthegc, CC BY-SA 4.0, Wikimedia Commons",
    "A5": "Riviera Tower at the Ellinikon, September 2025. Photo: Dimsar01, CC BY-SA 4.0, Wikimedia Commons",
}
SRC = {k: Image.open(P("images", f"{k}.jpg")).convert("RGB") for k in CROPS}

def plate_frame(key, t, push=0.08, drift=0.0):
    im = SRC[key]; _, _, pw, ph = PLATE
    cx, cy, z = CROPS[key]
    z = z * (1 + push * ease(t))
    aspect = pw / ph
    ch = im.height / z
    cw = ch * aspect
    if cw > im.width / z:
        cw = im.width / z; ch = cw / aspect
    x = cx * im.width + drift * im.width * (ease(t) - 0.5) - cw / 2
    y = cy * im.height - ch / 2
    x = max(0, min(im.width - cw, x)); y = max(0, min(im.height - ch, y))
    return im.resize((pw, ph), Image.LANCZOS, box=(x, y, x + cw, y + ch))

def draw_plate(img, key, t, push=0.08, drift=0.0):
    x, y, pw, ph = PLATE
    a = np.asarray(plate_frame(key, t, push, drift), np.float32) * 0.92 + np.array(INK, np.float32) * 0.08
    d = ImageDraw.Draw(img)
    d.rectangle((x - 6, y - 6, x + pw + 5, y + ph + 5), fill=DEEP)
    img.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), (x, y))
    for j, line in enumerate(wrap(d, CREDITS[key], F_SMALL, pw)):
        d.text((x, y + ph + 18 + j * 32), line, font=F_SMALL, fill=STEEL)

# ---------- the year ruler (signature) ----------
R_X0, R_X1, Y0, Y1 = 110, 970, 2000, 2026
THEN = 2004
def yx(year):
    return R_X0 + (R_X1 - R_X0) * (year - Y0) / (Y1 - Y0)

def ruler(img, y, reveal=1.0, marker=None, marker_col=HYPE, events=(), now_label=True, then_label=True, alpha=1.0):
    d = ImageDraw.Draw(img)
    xe = R_X0 + (R_X1 - R_X0) * ease(reveal)
    d.line((R_X0, y, xe, y), fill=mix(STEEL, alpha), width=3)
    for yr in range(Y0, Y1 + 1):
        x = yx(yr)
        if x > xe: break
        big = yr % 5 == 0
        d.line((x, y, x, y - (22 if big else 11)), fill=mix(STEEL if big else (80, 96, 110), alpha), width=3 if big else 2)
        if big:
            s = str(yr); d.text((x - tw(d, s, F_RULER) / 2, y + 12), s, font=F_RULER, fill=mix(STEEL, alpha))
    for yr, col in events:
        x = yx(yr); d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=mix(col, alpha))
    if then_label and reveal > 0.3:
        a = ease((reveal - 0.3) / 0.4) * alpha
        d.text((yx(THEN) - 8, y - 92), "Then", font=F_RULER, fill=mix(HYPE, a))
        d.text((yx(THEN) - 8, y - 64), str(THEN), font=F_RULER_BIG, fill=mix(HYPE, a))
    if now_label and reveal > 0.6:
        a = ease((reveal - 0.6) / 0.4) * alpha
        d.text((yx(2026) - tw(d, "Now", F_RULER) + 8, y - 92), "Now", font=F_RULER, fill=mix(REAL, a))
        d.text((yx(2026) - tw(d, "2026", F_RULER_BIG) + 8, y - 64), "2026", font=F_RULER_BIG, fill=mix(REAL, a))
    if marker is not None:
        x = yx(marker)
        d.polygon([(x - 14, y + 4), (x + 14, y + 4), (x, y - 22)], fill=mix(marker_col, alpha))
        d.line((x, y - 22, x, y - 40), fill=mix(marker_col, alpha), width=4)

# ---------- caption ----------
def caption(img, tsec):
    for a, b, c in CAPS:
        if a <= tsec < b:
            d = ImageDraw.Draw(img)
            k = ease((tsec - a) / 0.12)
            for j, line in enumerate(wrap(d, c, F_CAP, W - 2 * MARGIN)):
                d.text((MARGIN, CAP_Y + j * 74 + (1 - k) * 10), line, font=F_CAP, fill=mix(PAPER, 0.4 + 0.6 * k))
            return

def label(img, text, y=300, f=None, col=PAPER, a=1.0):
    ImageDraw.Draw(img).text((MARGIN, y), text, font=f or F_DISPLAY_M, fill=mix(col, a))

# ---------- scenes ----------
F_HOOK2 = font("ExpandedBlack", 62)
def scene_hook(t):
    img = canvas()
    draw_plate(img, "A1", t / 5.0, push=0.12, drift=0.05)
    ruler(img, 300, reveal=t / 1.1, marker=THEN if t > 0.6 else None, events=[(THEN, HYPE)] if t > 0.6 else [])
    d = ImageDraw.Draw(img); a = ease((t - 0.2) / 0.35)
    for j, line in enumerate(["The Olympics ended.", "What happened to", "the venues?"]):
        d.text((MARGIN, CAP_Y - 10 + j * 80), line, font=F_HOOK2, fill=mix(PAPER, a))
    return img

FIG_SIZE = 1040
def figure_frame(slot, lt):
    im = Image.open(os.path.join(CACHE, slot, f"f{min(299, int(lt * FPS)):04d}.png")).convert("RGB")
    im = im.resize((FIG_SIZE, int(im.height * FIG_SIZE / im.width)), Image.LANCZOS)
    img = canvas(); img.paste(im, ((W - FIG_SIZE) // 2, 255))
    return img

def scene_slot1(t):
    img = figure_frame("slot1", t)
    label(img, "Built on the old Athens airport", y=175, f=F_BODY, col=STEEL, a=ease(t / 0.5))
    return img

def scene_games(t):
    img = canvas(); draw_plate(img, "A2", t / 2.2, push=0.06)
    a = ease(t / 0.4)
    label(img, "13 to 29 August 2004", y=230, col=HYPE, a=a)
    label(img, "Seventeen days of Games", y=320, f=F_BODY, a=a)
    return img

def scene_cost(t):
    img = canvas(); d = ImageDraw.Draw(img); a = ease(t / 0.35)
    d.text((MARGIN, 420), "Estimated bill", font=F_BODY, fill=mix(STEEL, a))
    n = 11 * ease((t - 0.1) / 1.0)
    d.text((MARGIN, 470), f"Up to €{n:.0f} billion" if n >= 1 else "Up to €0 billion", font=F_DISPLAY_M, fill=mix(PAPER, a))
    d.text((MARGIN, 580), "for", font=F_BODY, fill=mix(STEEL, a))
    # seventeen squares, one per day of competition
    s = 46; g = 10
    for i in range(17):
        k = ease((t - 0.6 - i * 0.05) / 0.25)
        x = MARGIN + (i % 9) * (s + g); y = 650 + (i // 9) * (s + g)
        d.rectangle((x, y, x + s, y + s), fill=mix(HYPE, k * a))
    d.text((MARGIN, 790), "days of Olympic competition", font=F_BODY, fill=mix(PAPER, a))
    d.text((MARGIN, 870), "Estimates range from about €9 billion to €11 billion.", font=F_SMALL, fill=mix(STEEL, a))
    return img

def scene_photo(key, t, dur, text, col=PAPER):
    img = canvas(); draw_plate(img, key, t / dur, push=0.1)
    label(img, text, y=300, col=col, a=ease(t / 0.4))
    return img

def scene_quote(t):
    img = canvas(); d = ImageDraw.Draw(img); a = ease(t / 0.4)
    F_Q = font("MediumItalic", 64)
    lines = ["“It is not abandoned.", "It's just that nobody", "ever plays softball.”"]
    d.rectangle((MARGIN, 470, MARGIN + 8, 470 + 3 * 84 - 10), fill=mix(HYPE, a))
    for j, line in enumerate(lines):
        d.text((MARGIN + 40, 460 + j * 84), line, font=F_Q, fill=mix(PAPER, a))
    d.text((MARGIN + 40, 740), "A worker at the softball stadium, 2012, as reported by Business Insider (2014)", font=F_SMALL, fill=mix(STEEL, a))
    return img

def scene_decade(t):
    img = canvas(); d = ImageDraw.Draw(img); a = ease(t / 0.4)
    yr = THEN + 10 * ease((t - 0.3) / 1.6)
    ruler(img, 760, reveal=1.0, marker=yr, marker_col=REAL if yr > 2013.5 else HYPE, events=[(THEN, HYPE)] + ([(2014, REAL)] if yr > 2013.5 else []), now_label=False)
    label(img, "Ten years on", y=480, col=PAPER, a=a)
    d.text((MARGIN, 570), "Greece in a debt crisis", font=F_BODY, fill=mix(STEEL, a))
    return img

def scene_slot2(t):
    img = figure_frame("slot2", t)
    yr = THEN + 10 * ease((t - 0.2) / 1.0)
    ev = [(THEN, HYPE)] + ([(2014, REAL)] if t > 1.2 else [])
    ruler(img, 205, reveal=1.0, marker=yr, marker_col=REAL if t > 1.2 else HYPE, events=ev, now_label=False, then_label=False)
    d = ImageDraw.Draw(img)
    if t > 1.2:
        s = "€915 million deal"; d.text((yx(2014) - tw(d, s, F_RULER) / 2, 130), s, font=F_RULER, fill=mix(REAL, ease((t - 1.2) / 0.4)))
    return img

def scene_now(t):
    img = canvas(); draw_plate(img, "A5", t / 8.7, push=0.1, drift=0.0)
    yr = 2014 + 12 * ease((t - 0.2) / 1.4)
    ruler(img, 300, reveal=1.0, marker=yr, marker_col=REAL, events=[(THEN, HYPE), (2014, REAL)])
    return img

def scene_end(t):
    img = canvas(); d = ImageDraw.Draw(img); a = ease(t / 0.3)
    d.text((MARGIN, 760), "So what", font=F_END, fill=mix(PAPER, a))
    d.text((MARGIN, 880), "happened?", font=F_END, fill=mix(PAPER, a))
    d.text((MARGIN, 1040), "Sources are in the description.", font=F_SMALL, fill=mix(STEEL, a))
    return img

# phrase timings inside segment 2 (15.2 s start), by character share of the voiceover
EDL = [
    (0.0, 5.0, scene_hook),
    (5.0, 15.0, scene_slot1),
    (15.0, 17.2, scene_games),
    (17.2, 20.6, scene_cost),
    (20.6, 24.4, lambda t: scene_photo("A4", t, 3.8, "Softball stadium")),
    (24.4, 27.9, lambda t: scene_photo("A3", t, 3.5, "Canoe course")),
    (27.9, 33.8, scene_quote),
    (33.8, 40.0, scene_decade),
    (40.0, 50.0, scene_slot2),
    (50.0, STING_AT, scene_now),
    (STING_AT, 60.0, scene_end),
]
CUTS = [e[0] for e in EDL[1:]]

# ---------- finishing: vignette + grain ----------
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_r = np.sqrt(((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2)
VIGNETTE = np.clip(1.0 - 0.30 * np.clip(_r - 0.6, 0, None) ** 1.6, 0.6, 1.0)[..., None]
_rng = np.random.default_rng(3)
GRAIN = [(_rng.standard_normal((H // 2, W // 2, 1)) * 4.0).astype(np.float32) for _ in range(8)]

def finish(img, i):
    a = np.asarray(img, np.float32) * VIGNETTE
    a = np.clip(a + GRAIN[i % 8].repeat(2, 0).repeat(2, 1), 0, 255).astype(np.uint8)
    return Image.fromarray(a)

def render(i):
    ts = i / FPS
    for t0, t1, fn in EDL:
        if t0 <= ts < t1 or (t1 == DUR and ts >= t0):
            break
    img = fn(ts - t0)
    for c in CUTS:  # short dissolve through ink at each cut
        dt = ts - c
        if -0.067 <= dt < 0.067:
            img = Image.blend(canvas(), img, 0.3 + 0.7 * abs(dt) / 0.067)
    if 5.0 <= ts < STING_AT:
        caption(img, ts)
    return finish(img, i)

def ensure_figure_frames():
    for slot in ("slot1", "slot2"):
        d = os.path.join(CACHE, slot)
        if len(glob.glob(os.path.join(d, "f*.png"))) < 300:
            print("rendering figure", slot, flush=True)
            subprocess.run(["node", os.path.join(FIG, "render-frames.mjs"), slot, d], check=True)

# ---------- audio: VO + original synthesized score + whooshes ----------
SR = 48000

def synth_score():
    """Original ambient bed (no third-party music): slow minor pads + soft pulse."""
    n = int(SR * DUR); t = np.arange(n) / SR
    out = np.zeros(n, np.float32)
    # chord changes every ~7.5 s: Am - F - C - G (low register)
    roots = [110.0, 87.31, 130.81, 98.0]
    for k in range(8):
        s0 = k * 7.5; s1 = s0 + 8.5
        m = (t >= s0) & (t < s1)
        tt = t[m] - s0
        env = np.minimum(1, tt / 2.0) * np.minimum(1, np.maximum(0, (8.5 - tt) / 2.0))
        r = roots[k % 4]
        third = 1.189 if k % 4 == 0 else 1.26
        for f, g in [(r, 0.5), (r * third, 0.28), (r * 1.498, 0.32), (r * 2, 0.18)]:
            out[m] += (g * env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt))).astype(np.float32)
    # soft heartbeat pulse in the middle section (15-50 s)
    for b in np.arange(15.0, 50.0, 0.857):
        s = int(b * SR); L = int(0.25 * SR)
        e = np.exp(-np.arange(L) / (0.05 * SR))
        out[s:s + L] += (0.35 * e * np.sin(2 * np.pi * 55 * np.arange(L) / SR)).astype(np.float32)
    # simple one-pole low-pass for warmth
    y = np.zeros_like(out); a = 0.08
    for i in range(1, len(out)):
        y[i] = y[i - 1] + a * (out[i] - y[i - 1])
    return y / (np.abs(y).max() + 1e-9)

def whoosh(L=0.45):
    n = int(SR * L); rng = np.random.default_rng(9)
    noise = rng.standard_normal(n).astype(np.float32)
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    # band sweep via moving average of varying width
    y = np.convolve(noise, np.ones(12) / 12, mode="same") * env
    return y / (np.abs(y).max() + 1e-9)

def build_audio(path):
    n = int(SR * DUR)
    vo = np.zeros(n, np.float32)
    for k in range(5):
        with wave.open(P("vo", f"seg{k}.wav")) as w:
            sr = w.getframerate()
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if sr != SR:
            a = np.interp(np.arange(0, len(a), sr / SR), np.arange(len(a)), a).astype(np.float32)
        s = int(SEG_START[k] * SR); a = a[: n - s]
        vo[s:s + len(a)] += a
    vo /= (np.abs(vo).max() + 1e-9)
    # sidechain: duck music under speech
    envl = np.convolve(np.abs(vo), np.ones(SR // 20) / (SR // 20), mode="same")
    duck = 1.0 - 0.65 * np.clip(envl / (envl.max() * 0.25 + 1e-9), 0, 1)
    duck = np.convolve(duck, np.ones(SR // 10) / (SR // 10), mode="same")
    music = synth_score() * 0.16 * duck
    # music fade out under the sting, lift at the very end
    sfx = np.zeros(n, np.float32); wh = whoosh() * 0.12
    for c in CUTS:
        s = int((c - 0.25) * SR); sfx[s:s + len(wh)] += wh[: n - s]
    mix = vo * 0.9 + music + sfx
    mix /= (np.abs(mix).max() + 1e-9); mix *= 0.89
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

def loudnorm_two_pass(src, dst):
    """Measure then normalise to -14 LUFS / -1.5 dBTP (two-pass, linear)."""
    import json, re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
    flt = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
           f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-af", flt, "-ar", str(SR), dst], check=True)

def main():
    os.makedirs(P("out"), exist_ok=True)
    ensure_figure_frames()
    write_srt(P("out", "captions.srt"))
    build_audio(P("out", "mix_raw.wav"))
    loudnorm_two_pass(P("out", "mix_raw.wav"), P("out", "mix.wav"))
    out = P("out", "so-what-happened-02-athens-2004.mp4")
    ff = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", P("out", "mix.wav"),
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-t", str(DUR), "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for i in range(NF):
        ff.stdin.write(render(i).tobytes())
        if i % 300 == 0:
            print(f"frame {i}/{NF}", flush=True)
    ff.stdin.close(); ff.wait()
    print("wrote", out)

if __name__ == "__main__":
    main()
