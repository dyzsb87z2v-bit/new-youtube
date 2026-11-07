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

EDL = [
    still("I1", 0.0, 5.0, 1.02, 1.18, 0.10),
    ("clip", 5.0, 15.0, clip1),
    still("I1", 15.0, 20.2, 1.25, 1.40, -0.15),     # unveiling era, $5,000
    ("stat", 20.2, 28.4),                           # plan vs reality
    ("uk", 28.4, 31.2),                             # UK ban
    still("I3", 31.2, 35.6, 1.0, 1.10, 0.0),        # police
    still("I2", 35.6, 40.0, 1.0, 1.12, 0.08),       # tour groups
    ("clip", 40.0, 50.0, clip2),                    # + timeline overlay
    still("I5", 50.0, 60.0, 1.0, 1.15, -0.06),      # today
]

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
    elif kind == "clip":
        img = item[3].frame(int(lt * FPS))
        pill(img, "RECONSTRUCTION", y=1530, fg=WHITE, bgc=(30, 30, 34))
    elif kind == "stat":
        img = stat_card(lt)
    else:
        img = uk_card(lt)

    if 0 <= ts < 5.0:
        then_now(img, ts)
    if 40.0 <= ts < 50.0:
        timeline_overlay(img, ts - 40.0)
    if ts >= 50.0:
        then_now(img, ts - 50.0, now_highlight=True)
        if ts >= 55.5:
            d = ImageDraw.Draw(img)
            a = ease((ts - 55.5) / 0.5)
            pill(img, "BRAND ALIVE · ORIGINAL DISCONTINUED", y=420)
    # 6-frame fade between EDL blocks
    for item in EDL[1:]:
        dt = ts - item[1]
        if -0.1 <= dt < 0.1:
            k = abs(dt) / 0.1
            img = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), img, 0.35 + 0.65 * k)
    caption(img, ts)
    return img

def build_audio(path):
    sr = 48000
    mix = np.zeros(int(sr * DUR), np.float32)
    for k in range(5):
        with wave.open(P("vo", f"seg{k}.wav")) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        s = int(SEG_START[k] * sr)
        a = a[: len(mix) - s]
        mix[s:s + len(a)] += a
    peak = np.abs(mix).max() or 1
    mix = mix / peak * 0.89
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

def main():
    os.makedirs(P("out"), exist_ok=True)
    write_srt(P("out", "captions.srt"))
    build_audio(P("out", "vo_mix.wav"))
    out = P("out", "so-what-happened-01-segway.mp4")
    ff = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", P("out", "vo_mix.wav"),
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-t", str(DUR), "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    for i in range(NF):
        ff.stdin.write(render(i).tobytes())
        if i % 300 == 0:
            print(f"frame {i}/{NF}", flush=True)
    ff.stdin.close(); ff.wait()
    print("wrote", out)

if __name__ == "__main__":
    main()
