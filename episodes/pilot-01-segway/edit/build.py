#!/usr/bin/env python3
"""Build the 60-second cut of episode 01 (Segway) for "So What Happened?".

Free tools only: Python + Pillow + numpy + FFmpeg, Node + headless Chromium for the
isometric figure (anatomy skill), Archivo (SIL OFL) for type.

Design system:
  graphite-blue base, paper text, steel secondary,
  hype yellow = what was promised / THEN, reality rust = what happened / NOW.
  Signature: a year ruler (2000-2026) whose marker moves from THEN to NOW.

Inputs:  images/*.jpg (licensed stills), vo/seg0..4.wav, fonts/*.ttf,
         ../figure/ (isometric Segway; frames are rendered on demand)
Outputs: out/so-what-happened-01-segway.mp4, out/captions.srt
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

def font(name, size):
    return ImageFont.truetype(P("fonts", f"Archivo-{name}.ttf"), size)

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
    "In 2001, this was supposed to change how cities move. So what happened?",
    "Before launch, it had only a code name: Ginger. Steve Jobs reportedly said it could be as big as the PC.",
    "It was unveiled on live morning TV in December 2001, for about five thousand dollars. The plan: up to a hundred thousand sold in the first thirteen months. The reality: about a hundred and forty thousand, in nineteen years. The UK banned it from pavements. Instead of commuters, it found police officers and tour groups.",
    "In 2015, Beijing startup Ninebot bought the company. On July 15, 2020, the original Segway was made for the last time.",
    "Today, the Segway name lives on, on the electric scooters you see on city streets. The machine failed. The idea didn't.",
]
SEG_START = [0.05, 5.3, 15.0, 40.0, 50.4]

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
    "I1": (0.40, 0.48, 1.00),
    "I2": (0.33, 0.58, 1.55),
    "I3": (0.55, 0.62, 1.00),
    "I5": (0.72, 0.56, 1.05),
}
CREDITS = {
    "I1": "Dean Kamen with the Segway, 2002. Photo: redjar, CC BY-SA 2.0, Wikimedia Commons",
    "I2": "Segway tour, Stockholm, 2011. Photo: Rosser1954, CC BY-SA 3.0, Wikimedia Commons",
    "I3": "City police, Prague, 2012. Photo: AlfvanBeem, CC0, Wikimedia Commons",
    "I5": "Segway-made rental scooter, 2018. Photo: Vogler, CC BY-SA 4.0, Wikimedia Commons",
}
SRC = {k: Image.open(P("images", f"{k}.jpg")).convert("RGB") for k in CROPS}

def plate_frame(key, t, push=0.08, drift=0.0):
    """Photo cropped to the plate aspect with a slow push-in (t in 0..1)."""
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

def draw_plate(img, key, t, push=0.08, drift=0.0, alpha=1.0):
    x, y, pw, ph = PLATE
    ph_img = plate_frame(key, t, push, drift)
    # gentle grade so photos sit in the palette
    a = np.asarray(ph_img, np.float32)
    a = a * 0.92 + np.array(INK, np.float32) * 0.08
    ph_img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.rectangle((x - 6, y - 6, x + pw + 5, y + ph + 5), fill=DEEP)
    if alpha < 1:
        ph_img = Image.blend(Image.new("RGB", ph_img.size, INK), ph_img, alpha)
    img.paste(ph_img, (x, y))
    d.text((x, y + ph + 18), CREDITS[key], font=F_SMALL, fill=STEEL)

# ---------- the year ruler (signature) ----------
R_X0, R_X1, Y0, Y1 = 110, 970, 2000, 2026
def yx(year):
    return R_X0 + (R_X1 - R_X0) * (year - Y0) / (Y1 - Y0)

def ruler(img, y, reveal=1.0, marker=None, marker_col=HYPE, events=(), now_label=True, then_label=True, alpha=1.0):
    """Baseline with a tick per year, majors every 5. `marker` is a (fractional) year."""
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
        x = yx(yr)
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=mix(col, alpha))
    if then_label and reveal > 0.3:
        a = ease((reveal - 0.3) / 0.4) * alpha
        d.text((yx(2001) - 8, y - 92), "Then", font=F_RULER, fill=mix(HYPE, a))
        d.text((yx(2001) - 8, y - 64), "2001", font=F_RULER_BIG, fill=mix(HYPE, a))
    if now_label and reveal > 0.6:
        a = ease((reveal - 0.6) / 0.4) * alpha
        s = "2026"; x = yx(2026) - tw(d, s, F_RULER_BIG) + 8
        d.text((yx(2026) - tw(d, "Now", F_RULER) + 8, y - 92), "Now", font=F_RULER, fill=mix(REAL, a))
        d.text((x, y - 64), s, font=F_RULER_BIG, fill=mix(REAL, a))
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

# ---------- scenes ----------
def scene_hook(t):
    img = canvas()
    draw_plate(img, "I1", t / 5.0, push=0.12, drift=0.04)
    ruler(img, 300, reveal=t / 1.1, marker=2001 if t > 0.6 else None, events=[(2001, HYPE)] if t > 0.6 else [])
    d = ImageDraw.Draw(img)
    a = ease((t - 0.2) / 0.35)
    for j, line in enumerate(["Supposed to change", "how cities move."]):
        d.text((MARGIN, CAP_Y - 30 + j * 88), line, font=F_HOOK, fill=mix(PAPER, a))
    return img

FIG_SIZE = 1040
def figure_frame(slot, lt):
    path = os.path.join(CACHE, slot, f"f{min(299, int(lt * FPS)):04d}.png")
    im = Image.open(path).convert("RGB")
    im = im.resize((FIG_SIZE, int(im.height * FIG_SIZE / im.width)), Image.LANCZOS)
    img = canvas()
    img.paste(im, ((W - FIG_SIZE) // 2, 255))
    return img

def scene_slot1(t):
    img = figure_frame("slot1", t)
    d = ImageDraw.Draw(img)
    a = ease(t / 0.5)
    d.text((MARGIN, 175), "Before launch it was a secret.", font=F_BODY, fill=mix(STEEL, a))
    return img

def scene_unveil(t):
    img = canvas()
    draw_plate(img, "I1", t / 5.2, push=0.1, drift=-0.06)
    d = ImageDraw.Draw(img)
    a = ease(t / 0.4)
    d.text((MARGIN, 230), "December 2001", font=F_DISPLAY_M, fill=mix(HYPE, a))
    d.text((MARGIN, 320), "About $5,000 each", font=F_BODY, fill=mix(PAPER, a))
    return img

def scene_rate(t):
    """The plan vs what happened. Bars compare sales per month:
    100,000 / 13 = about 7,700 a month; about 140,000 / (12 x 18.6 years) = about 630 a month."""
    img = canvas(); d = ImageDraw.Draw(img)
    planned, real = 100000 / 13, 140000 / (12 * 18.6)
    full = W - 2 * MARGIN
    a = ease(t / 0.4)
    d.text((MARGIN, 330), "The plan", font=F_BODY, fill=mix(HYPE, a))
    n = int(round(100000 * ease((t - 0.2) / 1.2), -3))
    d.text((MARGIN, 380), f"{n:,}", font=F_DISPLAY, fill=mix(PAPER, a))
    d.text((MARGIN, 540), "in the first 13 months", font=F_BODY, fill=mix(PAPER, a))
    bw = full * ease((t - 0.2) / 1.2)
    d.rectangle((MARGIN, 615, MARGIN + bw, 650), fill=mix(HYPE, a))
    d.text((MARGIN, 665), "About 7,700 a month", font=F_SMALL, fill=mix(STEEL, a))
    if t > 3.4:
        b = ease((t - 3.4) / 0.4)
        d.text((MARGIN, 790), "What happened", font=F_BODY, fill=mix(REAL, b))
        m = int(round(140000 * ease((t - 3.5) / 1.0), -3))
        d.text((MARGIN, 840), f"{m:,}", font=F_DISPLAY, fill=mix(PAPER, b))
        d.text((MARGIN, 1000), "in nearly 19 years", font=F_BODY, fill=mix(PAPER, b))
        rw = full * real / planned * ease((t - 3.5) / 1.0)
        d.rectangle((MARGIN, 1075, MARGIN + max(rw, 2), 1110), fill=mix(REAL, b))
        d.text((MARGIN, 1125), "About 630 a month", font=F_SMALL, fill=mix(STEEL, b))
    return img

def scene_uk(t):
    img = canvas(); d = ImageDraw.Draw(img)
    a = ease(t / 0.35)
    d.text((MARGIN, 520), "Not allowed", font=F_DISPLAY_M, fill=mix(PAPER, a))
    d.text((MARGIN, 610), "on UK pavements", font=F_DISPLAY_M, fill=mix(REAL, a))
    y = 820   # a kerb drawn as two slabs and joint lines
    d.rectangle((MARGIN, y, W - MARGIN, y + 18), fill=mix((60, 75, 90), a))
    d.rectangle((MARGIN, y + 18, W - MARGIN, y + 70), fill=mix((40, 52, 64), a))
    for x in range(MARGIN + 160, W - MARGIN, 160):
        d.line((x, y, x, y + 18), fill=mix(INK, a), width=3)
    d.text((MARGIN, 920), "UK Department for Transport, 2006. Upheld by the High Court, 2011.", font=F_SMALL, fill=mix(STEEL, a))
    return img

def scene_photo(key, t, dur, label):
    img = canvas()
    draw_plate(img, key, t / dur, push=0.1)
    d = ImageDraw.Draw(img)
    a = ease(t / 0.4)
    d.text((MARGIN, 300), label, font=F_DISPLAY_M, fill=mix(PAPER, a))
    return img

def scene_slot2(t):
    img = figure_frame("slot2", t)
    # the ruler walks the marker 2001 -> 2015 -> 2020 in step with the voice
    yr = 2001 + 14 * ease((t - 0.2) / 1.0) + 5 * ease((t - 3.6) / 1.0)
    ev = [(2001, HYPE)] + ([(2015, STEEL)] if t > 1.0 else []) + ([(2020, REAL)] if t > 4.6 else [])
    ruler(img, 205, reveal=1.0, marker=yr, marker_col=REAL if t > 4.6 else HYPE, events=ev, now_label=False, then_label=False)
    d = ImageDraw.Draw(img)
    if t > 1.0:
        d.text((yx(2015) - 60, 130), "Ninebot", font=F_RULER, fill=mix(STEEL, ease((t - 1.0) / 0.4)))
    if t > 4.6:
        s = "Last one made"; d.text((yx(2020) - tw(d, s, F_RULER) / 2 + 20, 130), s, font=F_RULER, fill=mix(REAL, ease((t - 4.6) / 0.4)))
    return img

def scene_now(t):
    img = canvas()
    draw_plate(img, "I5", t / 8.3, push=0.12, drift=-0.05)
    yr = 2020 + 6 * ease((t - 0.2) / 1.4)
    ruler(img, 300, reveal=1.0, marker=yr, marker_col=REAL, events=[(2001, HYPE), (2020, REAL)])
    return img

def scene_end(t):
    img = canvas(); d = ImageDraw.Draw(img)
    a = ease(t / 0.35)
    d.text((MARGIN, 760), "So what", font=F_END, fill=mix(PAPER, a))
    d.text((MARGIN, 880), "happened?", font=F_END, fill=mix(PAPER, a))
    ruler(img, 1120, reveal=a, marker=2026 if a > 0.9 else None, marker_col=REAL, events=[], then_label=False, now_label=False, alpha=a)
    d.text((MARGIN, 1200), "Sources are in the description.", font=F_SMALL, fill=mix(STEEL, a))
    return img

EDL = [
    (0.0, 5.0, scene_hook),
    (5.0, 15.0, scene_slot1),
    (15.0, 20.2, scene_unveil),
    (20.2, 28.4, scene_rate),
    (28.4, 31.2, scene_uk),
    (31.2, 35.6, lambda t: scene_photo("I3", t, 4.4, "Police officers")),
    (35.6, 40.0, lambda t: scene_photo("I2", t, 4.4, "Tour groups")),
    (40.0, 50.0, scene_slot2),
    (50.0, 58.3, scene_now),
    (58.3, 60.0, scene_end),
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
    if 5.0 <= ts < 58.3:
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
    out = P("out", "so-what-happened-01-segway.mp4")
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
