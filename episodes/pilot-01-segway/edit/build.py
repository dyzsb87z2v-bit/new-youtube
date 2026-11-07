#!/usr/bin/env python3
"""Build the 60-second cut of pilot 01 (Segway) for "So What Happened?".

Free tools only: Python + Pillow + numpy + FFmpeg, Inter font (SIL OFL).

Inputs (relative to this folder):
  images/I1.jpg I2.jpg I3.jpg I5.jpg   licensed stills (see ../sources.csv)
  vo/seg0.wav .. seg4.wav               voiceover, one file per script row
  clips/clip1.mp4, clips/clip2.mp4      OPTIONAL 10s reconstruction clips;
                                        a labelled placeholder is used if missing

Outputs:
  out/so-what-happened-01-segway.mp4    1080x1920, 30 fps, 60.0 s
  out/captions.srt                      captions (also burned into the video)

Usage:  python3 build.py
"""
import os, subprocess, wave, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(HERE, *a)
W, H, FPS, DUR = 1080, 1920, 30, 60.0
NF = int(FPS * DUR)

# ---------- style ----------
BG = (12, 12, 14)
ACCENT = (255, 181, 71)        # amber
WHITE = (245, 245, 240)
FONT_DIR = "/usr/share/fonts/opentype/inter/"
def font(weight, size):
    return ImageFont.truetype(FONT_DIR + f"Inter-{weight}.otf", size)
F_CAP = font("Black", 66)
F_CARD_SMALL = font("SemiBold", 34)
F_CARD_BIG = font("Black", 92)
F_LABEL = font("Bold", 30)
F_CREDIT = font("Medium", 24)
F_STAT_SMALL = font("Bold", 44)
F_STAT_BIG = font("Black", 150)
F_TL_YEAR = font("Black", 64)
F_TL_TXT = font("SemiBold", 34)

# Safe zone: keep text between y=180 and y=1600.
CAPTION_Y = 1330

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
    """Split each segment into ~4-word chunks timed by character count."""
    out = []
    for txt, st, du in zip(SEG_TEXT, SEG_START, SEG_DUR):
        words = txt.split()
        chunks, cur = [], []
        for w in words:
            cur.append(w)
            if len(cur) >= 4 or w.endswith((".", "?", ":", ",")) and len(cur) >= 2:
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

def text_w(d, s, f):
    b = d.textbbox((0, 0), s, font=f); return b[2] - b[0]

def draw_center(d, y, s, f, fill, stroke=0, stroke_fill=(0, 0, 0)):
    d.text(((W - text_w(d, s, f)) / 2, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)

def wrap(d, s, f, maxw):
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if text_w(d, t, f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def vertical_plate(path):
    """Landscape/portrait still -> 1.25x oversized 9:16 plate: blurred cover bg + sharp fitted fg."""
    im = Image.open(path).convert("RGB")
    PW, PH = int(W * 1.25), int(H * 1.25)
    s = max(PW / im.width, PH / im.height)
    bg = im.resize((int(im.width * s) + 1, int(im.height * s) + 1)).filter(ImageFilter.GaussianBlur(40))
    bg = bg.crop(((bg.width - PW) // 2, (bg.height - PH) // 2, (bg.width - PW) // 2 + PW, (bg.height - PH) // 2 + PH))
    bg = Image.blend(bg, Image.new("RGB", bg.size, BG), 0.45)
    s2 = min(PW / im.width, PH * 0.62 / im.height)
    fg = im.resize((int(im.width * s2), int(im.height * s2)), Image.LANCZOS)
    bg.paste(fg, ((PW - fg.width) // 2, (PH - fg.height) // 2 - int(PH * 0.06)))
    return bg

def kenburns(plate, t, z0=1.0, z1=1.12, dx=0.0):
    """t in [0,1]; slow push-in on an oversized plate."""
    z = z0 + (z1 - z0) * ease(t)
    cw, ch = plate.width / (1.25 * z) * 1.0, plate.height / (1.25 * z)
    cx = plate.width / 2 + dx * plate.width * (ease(t) - 0.5)
    cy = plate.height / 2
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return plate.resize((W, H), Image.BICUBIC, box=box)

def credit(img, s):
    d = ImageDraw.Draw(img)
    d.text((40, 1560), s, font=F_CREDIT, fill=(200, 200, 195), stroke_width=2, stroke_fill=(0, 0, 0))

def pill(img, s, y=210, fg=(15, 15, 15), bgc=ACCENT):
    d = ImageDraw.Draw(img)
    tw = text_w(d, s, F_LABEL)
    x0 = (W - tw) / 2 - 26
    d.rounded_rectangle((x0, y, x0 + tw + 52, y + 56), radius=28, fill=bgc)
    d.text((x0 + 26, y + 10), s, font=F_LABEL, fill=fg)

# ---------- clip sources ----------
class Clip:
    """10s clip read via ffmpeg, or a labelled placeholder."""
    def __init__(self, path, title):
        self.path, self.title = path, title
        self.frames = None
        if os.path.exists(path):
            raw = subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-i", path, "-t", "10", "-vf",
                 f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
            n = len(raw) // (W * H * 3)
            self.frames = np.frombuffer(raw, np.uint8)[: n * W * H * 3].reshape(n, H, W, 3)

    def frame(self, i):
        if self.frames is not None and len(self.frames):
            return Image.fromarray(self.frames[min(i, len(self.frames) - 1)])
        img = Image.new("RGB", (W, H), (22, 24, 30))
        d = ImageDraw.Draw(img)
        for k in range(0, H, 6):  # subtle scanlines so it reads as placeholder
            d.line((0, k, W, k), fill=(26, 28, 35))
        draw_center(d, 420, "PLACEHOLDER", F_STAT_SMALL, (120, 125, 140))
        for j, line in enumerate(wrap(d, self.title, F_TL_TXT, 900)):
            draw_center(d, 490 + j * 46, line, F_TL_TXT, (150, 155, 170))
        return img

# ---------- motion pieces ----------
def stat_card(t):
    """15-40 s section stat: PLAN vs REALITY (t = seconds into the card)."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    a = ease(t / 0.5)
    draw_center(d, 520, "THE PLAN", F_STAT_SMALL, tuple(int(c * a) for c in (170, 170, 165)))
    n = int(100000 * ease(t / 1.2))
    draw_center(d, 590, f"{n:,}", F_STAT_BIG, tuple(int(c * a) for c in WHITE))
    draw_center(d, 770, "in 13 months", F_STAT_SMALL, tuple(int(c * a) for c in (170, 170, 165)))
    if t > 3.6:
        b = ease((t - 3.6) / 0.5)
        draw_center(d, 960, "THE REALITY", F_STAT_SMALL, tuple(int(c * b) for c in ACCENT))
        m = int(140000 * ease((t - 3.6) / 1.2))
        draw_center(d, 1030, f"~{m:,}", F_STAT_BIG, tuple(int(c * b) for c in ACCENT))
        draw_center(d, 1210, "in 19 years", F_STAT_SMALL, tuple(int(c * b) for c in ACCENT))
    return img

def uk_card(t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    a = ease(t / 0.4)
    draw_center(d, 640, "UNITED KINGDOM", F_STAT_SMALL, tuple(int(c * a) for c in (170, 170, 165)))
    draw_center(d, 710, "BANNED", F_STAT_BIG, tuple(int(c * a) for c in WHITE))
    draw_center(d, 890, "from pavements", F_STAT_SMALL, tuple(int(c * a) for c in WHITE))
    return img

TL = [(2001, "Unveiled on live TV"), (2015, "Bought by Ninebot"), (2020, "Original Segway ends")]
TL_T = [0.3, 1.0, 4.5]  # seconds into the 40-50 block when each point appears

def timeline_overlay(img, t):
    """Lower-third timeline drawn over clip 2 (t = seconds into block)."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rectangle((0, 780, W, 1160), fill=(8, 8, 10, 190))
    x0, x1, y = 200, 880, 880
    prog = ease((t - 0.2) / 5.0)
    d.line((x0, y, x0 + (x1 - x0) * prog, y), fill=ACCENT + (255,), width=6)
    for k, ((yr, lab), at) in enumerate(zip(TL, TL_T)):
        if t < at: continue
        a = int(255 * ease((t - at) / 0.4))
        x = x0 + (x1 - x0) * k / 2
        d.ellipse((x - 16, y - 16, x + 16, y + 16), fill=ACCENT + (a,))
        s = str(yr); d.text((x - text_w(d, s, F_TL_YEAR) / 2, y + 30), s, font=F_TL_YEAR, fill=WHITE + (a,))
        for j, line in enumerate(wrap(d, lab, F_TL_TXT, 260)):
            d.text((x - text_w(d, line, F_TL_TXT) / 2, y + 110 + j * 42), line, font=F_TL_TXT, fill=(200, 200, 195, a))
    img.paste(ov, (0, 0), ov)

def then_now(img, t, now_highlight=False):
    """Date card at the top. t = seconds since card start."""
    d = ImageDraw.Draw(img)
    a = ease(t / 0.4)
    y = 200
    box = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(box)
    bd.rounded_rectangle((90, y, W - 90, y + 190), radius=24, fill=(10, 10, 12, int(200 * a)))
    img.paste(box, (0, 0), box)
    col_then = tuple(int(c * a) for c in (WHITE if not now_highlight else (150, 150, 145)))
    col_now = tuple(int(c * a) for c in (ACCENT if (now_highlight or t > 1.2) else WHITE))
    d.text((150, y + 22), "THEN", font=F_CARD_SMALL, fill=col_then)
    d.text((150, y + 62), "2001", font=F_CARD_BIG, fill=col_then)
    d.text((W / 2 - 22, y + 70), "→", font=F_CARD_BIG, fill=tuple(int(c * a) for c in (120, 120, 115)))
    nw = text_w(d, "2026", F_CARD_BIG)
    d.text((W - 150 - nw, y + 22), "NOW", font=F_CARD_SMALL, fill=col_now)
    d.text((W - 150 - nw, y + 62), "2026", font=F_CARD_BIG, fill=col_now)

def caption(img, tsec):
    for a, b, c in CAPS:
        if a <= tsec < b:
            d = ImageDraw.Draw(img)
            lines = wrap(d, c, F_CAP, 940)
            for j, line in enumerate(lines):
                # highlight numbers/years in amber
                fill = ACCENT if any(ch.isdigit() for ch in line) else WHITE
                draw_center(d, CAPTION_Y + j * 82, line, F_CAP, fill, stroke=6)
            return

# ---------- edit decision list ----------
plates = {k: vertical_plate(P("images", f"{k}.jpg")) for k in ["I1", "I2", "I3", "I5"]}
clip1 = Clip(P("clips", "clip1.mp4"), "Clip 1 (Milad) · 10s · early-2000s city at dawn, silhouetted rider on a self-balancing transporter")
clip2 = Clip(P("clips", "clip2.mp4"), "Clip 2 (Milad) · 10s · dusty warehouse of unbranded self-balancing transporters")

CREDITS = {
    "I1": "Photo: redjar · CC BY-SA 2.0 · Wikimedia Commons",
    "I2": "Photo: Rosser1954 · CC BY-SA 3.0 · Wikimedia Commons",
    "I3": "Photo: AlfvanBeem · CC0 · Wikimedia Commons",
    "I5": "Photo: Vogler · CC BY-SA 4.0 · Wikimedia Commons (2018)",
}

def still(key, t0, t1, z0=1.0, z1=1.12, dx=0.0):
    return ("still", t0, t1, key, z0, z1, dx)


# ---------- motion replacements for the two clip slots ----------
F_CODE_SMALL = font("SemiBold", 40)
F_CODE_BIG = font("Black", 190)
F_QUOTE = font("Bold", 58)
F_QUOTE_SRC = font("Medium", 32)
F_BRAND = font("Black", 84)

def codename_motion(t):
    """5-15 s: 'CODE NAME: GINGER' reveal, then the Jobs quote card (no fake footage)."""
    bgp = kenburns(plates_dark["I6"] if "I6" in plates_dark else plates_dark["I1"], t / 10.0, 1.3, 1.45, 0.2)
    img = bgp.copy()
    d = ImageDraw.Draw(img)
    if t < 4.6:
        a = ease(t / 0.5)
        draw_center(d, 640, "BEFORE LAUNCH · 2001", F_CODE_SMALL, tuple(int(c * a) for c in (170, 170, 165)))
        word = "GINGER"
        n = int(len(word) * ease((t - 0.6) / 1.2)) if t > 0.6 else 0
        shown = word[:n]
        if shown:
            # letter-spaced reveal
            sp = 18
            ws = [text_w(d, ch, F_CODE_BIG) for ch in word]
            total = sum(ws) + sp * (len(word) - 1)
            x = (W - total) / 2
            for k, ch in enumerate(shown):
                d.text((x, 720), ch, font=F_CODE_BIG, fill=ACCENT)
                x += ws[k] + sp
        if t > 2.2:
            b = ease((t - 2.2) / 0.5)
            draw_center(d, 960, "the secret code name", F_CODE_SMALL, tuple(int(c * b) for c in WHITE))
        fade = 1 - ease((t - 4.2) / 0.4)
        if fade < 1:
            img = Image.blend(bgp, img, max(0.0, fade))
    else:
        tq = t - 4.6
        a = ease(tq / 0.5)
        lines = ["“As big a deal", "as the PC.”"]
        for j, line in enumerate(lines):
            draw_center(d, 700 + j * 78, line, F_QUOTE, tuple(int(c * a) for c in WHITE))
        draw_center(d, 880, "Steve Jobs, as reported by TIME (2001)", F_QUOTE_SRC, tuple(int(c * a) for c in (170, 170, 165)))
        d.line((W / 2 - 60, 660, W / 2 + 60, 660), fill=tuple(int(c * a) for c in ACCENT), width=5)
    return img

def timeline_bg(t):
    return kenburns(plates_dark["I2"], t / 10.0, 1.15, 1.3, -0.1)

def dark_plate(path):
    pl = vertical_plate(path).filter(ImageFilter.GaussianBlur(14))
    return Image.blend(pl, Image.new("RGB", pl.size, BG), 0.6)

# ---------- finishing: grade, vignette, grain ----------
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
_r = np.sqrt(((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2)
VIGNETTE = np.clip(1.0 - 0.38 * np.clip(_r - 0.55, 0, None) ** 1.6, 0.55, 1.0)[..., None]
_rng = np.random.default_rng(3)
GRAIN = [(_rng.standard_normal((H // 2, W // 2, 1)) * 5.5).astype(np.float32) for _ in range(8)]

def finish(img, i):
    a = np.asarray(img, np.float32)
    # gentle filmic grade: lift shadows a touch, warm highlights, slight contrast curve
    a = a / 255.0
    a = a * a * (3 - 2 * a) * 0.25 + a * 0.75
    a[..., 0] *= 1.02; a[..., 2] *= 0.98
    a = a * 255.0 * VIGNETTE
    g = GRAIN[i % len(GRAIN)].repeat(2, 0).repeat(2, 1)
    a = np.clip(a + g, 0, 255).astype(np.uint8)
    return Image.fromarray(a)

def hook_text(img, t):
    """0-2.6 s: big hook line in the middle of the frame."""
    if t >= 2.6:
        return
    a = ease(t / 0.3) * (1 - ease((t - 2.2) / 0.4))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for j, line in enumerate(["SUPPOSED TO CHANGE", "HOW CITIES MOVE."]):
        f = F_BRAND
        d.text(((W - text_w(d, line, f)) / 2, 760 + j * 100), line, font=f,
               fill=(255, 255, 255, int(255 * a)), stroke_width=7, stroke_fill=(0, 0, 0, int(220 * a)))
    img.paste(ov, (0, 0), ov)

def brand_sting(img, t):
    """58.3-60 s: channel sting after the answer has been given."""
    a = ease(t / 0.4)
    ov = Image.new("RGBA", (W, H), (BG[0], BG[1], BG[2], int(235 * a)))
    d = ImageDraw.Draw(ov)
    draw = lambda y, s, f, c: d.text(((W - text_w(d, s, f)) / 2, y), s, font=f, fill=c + (int(255 * a),))
    draw(820, "SO WHAT", F_BRAND, WHITE)
    draw(915, "HAPPENED?", F_BRAND, ACCENT)
    draw(1040, "Sources in the description", F_CREDIT, (170, 170, 165))
    img.paste(ov, (0, 0), ov)

# ---------- edit decision list ----------
plates = {k: vertical_plate(P("images", f"{k}.jpg")) for k in ["I1", "I2", "I3", "I5"]}
plates_dark = {k: dark_plate(P("images", f"{k}.jpg")) for k in ["I1", "I2"]}
clip1 = Clip(P("clips", "clip1.mp4"), "")
clip2 = Clip(P("clips", "clip2.mp4"), "")

EDL = [
    still("I1", 0.0, 5.0, 1.02, 1.18, 0.10),
    ("slot1", 5.0, 15.0, clip1),                    # reconstruction clip 1, or code-name motion
    still("I1", 15.0, 20.2, 1.25, 1.40, -0.15),     # unveiling era, $5,000
    ("stat", 20.2, 28.4),                           # plan vs reality
    ("uk", 28.4, 31.2),                             # UK ban
    still("I3", 31.2, 35.6, 1.0, 1.10, 0.0),        # police
    still("I2", 35.6, 40.0, 1.0, 1.12, 0.08),       # tour groups
    ("slot2", 40.0, 50.0, clip2),                   # reconstruction clip 2, or graded bg; timeline on top
    still("I5", 50.0, 60.0, 1.0, 1.15, -0.06),      # today
]
CUTS = [it[1] for it in EDL[1:]]
STING_AT = 58.3

def render(i):
    ts = i / FPS
    for item in EDL:
        kind, t0, t1 = item[0], item[1], item[2]
        if t0 <= ts < t1 or (item is EDL[-1] and ts >= t0):
            break
    lt = ts - t0
    if kind == "still":
        _, _, _, key, z0, z1, dx = item
        img = kenburns(plates[key], lt / (t1 - t0), z0, z1, dx)
        credit(img, CREDITS[key])
    elif kind in ("slot1", "slot2"):
        clip = item[3]
        if clip.frames is not None:
            img = clip.frame(int(lt * FPS))
            pill(img, "RECONSTRUCTION", y=1530, fg=WHITE, bgc=(30, 30, 34))
        elif kind == "slot1":
            img = codename_motion(lt)
        else:
            img = timeline_bg(lt)
    elif kind == "stat":
        img = stat_card(lt)
    else:
        img = uk_card(lt)

    if 0 <= ts < 5.0:
        then_now(img, ts)
        hook_text(img, ts)
    if 40.0 <= ts < 50.0:
        timeline_overlay(img, ts - 40.0)
    if 50.0 <= ts < STING_AT:
        then_now(img, ts - 50.0, now_highlight=True)
        if ts >= 55.5:
            pill(img, "BRAND ALIVE · ORIGINAL DISCONTINUED", y=420)
    # quick dip between blocks
    for c in CUTS:
        dt = ts - c
        if -0.1 <= dt < 0.1:
            img = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), img, 0.35 + 0.65 * abs(dt) / 0.1)
    if ts < STING_AT:
        caption(img, ts)
    else:
        brand_sting(img, ts - STING_AT)
    return finish(img, i)

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
