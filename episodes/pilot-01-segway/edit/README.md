# Edit — pilot 01 (Segway)

Builds the full 60-second video with free tools only: Python, Pillow, numpy and FFmpeg; Node and headless Chromium for the isometric figure; Archivo (SIL OFL, `fonts/OFL.txt`) for type.

```
python3 build.py      # -> out/so-what-happened-01-segway.mp4 + out/captions.srt (~1 min)
```

## What to drop in
| File | What | Status |
|---|---|---|
| `clips/clip1.mp4` | Reconstruction clip 1, 10 s, 9:16 (5–15 s) | Optional: without it, an animated motion sequence is used |
| `clips/clip2.mp4` | Reconstruction clip 2, 10 s, 9:16 (40–50 s); timeline overlay is drawn on top | Optional: without it, an animated motion sequence is used |
| `vo/seg0.wav … seg4.wav` | One voiceover file per script row | Scratch voice now (Kokoro TTS, Apache-2.0, voice `am_michael`, speed 1.12). Replace with final voice, same file names |

Clips are read from the first 10 s and center-cropped to 1080×1920. Each VO file must fit its slot: 0–5 s, 5.3–15 s, 15–40 s, 40–50 s, 50.4–60 s.

## Images
`images/` holds the four Commons stills from `../sources.csv` (resized to max 2000 px). The credit line for each is burned into the frame and must also be in the video description.

## Design system
- **Palette:** graphite blue `#172029` (page), paper `#E6ECEF` (text), steel `#7F909E` (secondary).
- **Two accents with fixed meanings:** hype yellow `#F2C94C` is what was promised, or THEN; reality rust `#C8553D` is what happened, or NOW.
- **Type:** Archivo Expanded Black/ExtraBold for display, Archivo SemiBold/Medium for captions and labels. Sentence case, left aligned, 60 px margin.
- **Signature:** a year ruler from 2000 to 2026. Its marker starts at THEN (2001) and ends at NOW (2026); in the 40–50 s slot it walks through the events.
- **Photos:** framed plates of a single size (1000×820) with the credit line under each. No blurred letterboxing.
- **Explainer:** an isometric cutaway of the Segway (`../figure/segway.mjs`, anatomy skill). The lit part is the balance sensor board. Slot 1 shows it leaning and driving; slot 2 shows it slowing down and switching off.

## Pipeline
1. `../figure/render-frames.mjs slot1|slot2` renders 300 frames per slot. `build.py` runs it automatically when `out/frames/` is empty.
2. `build.py` composes the scenes, burns in captions, adds vignette and grain, mixes the voice with the original synthesized score, normalises loudness in two passes, and encodes the result.

## Known limits
- The final AAC file measures about −15 LUFS against a −14 target.
- The voice is a stock Kokoro voice. Drop in new `vo/seg*.wav` files to replace it.
