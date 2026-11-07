# Edit — pilot 01 (Segway)

Builds the full 60-second video with free tools only (Python, Pillow, numpy, FFmpeg, Inter font).

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

## Finishing (automatic)
- Filmic grade, vignette and film grain on every frame.
- Hook line (0–2.6 s), THEN/NOW card, and a channel sting after the answer (58.3–60 s).
- Original synthesized ambient score, ducked under the voice, plus soft whooshes on cuts. No third-party music, so there is nothing to license.
- Two-pass loudness normalisation to −14 LUFS before encoding. The final AAC file measures about −15 LUFS.
- If `clips/clip1.mp4` / `clip2.mp4` are absent, slot 1 shows a "code name GINGER" plus Jobs-quote motion sequence, and slot 2 shows a graded still under the timeline. In that case no AI footage is used and no RECONSTRUCTION label appears.
