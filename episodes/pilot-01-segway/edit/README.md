# Edit — pilot 01 (Segway)

Builds the full 60-second video with free tools only (Python, Pillow, numpy, FFmpeg, Inter font).

```
python3 build.py      # -> out/so-what-happened-01-segway.mp4 + out/captions.srt (~1 min)
```

## What to drop in
| File | What | Status |
|---|---|---|
| `clips/clip1.mp4` | Reconstruction clip 1, 10 s, 9:16 (5–15 s) | **Milad**: placeholder until added |
| `clips/clip2.mp4` | Reconstruction clip 2, 10 s, 9:16 (40–50 s); timeline overlay is drawn on top | **Milad**: placeholder until added |
| `vo/seg0.wav … seg4.wav` | One voiceover file per script row | Scratch voice now (Kokoro TTS, Apache-2.0, voice `am_michael`, speed 1.12). Replace with final voice, same file names |

Clips are read from the first 10 s and center-cropped to 1080×1920. Each VO file must fit its slot: 0–5 s, 5.3–15 s, 15–40 s, 40–50 s, 50.4–60 s.

## Images
`images/` holds the four Commons stills from `../sources.csv` (resized to max 2000 px). The credit line for each is burned into the frame and must also be in the video description.

## Known limits
- Loudness lands near −16 LUFS (target −14). Fine for a rough cut; re-check once the final voice is in.
- No music yet. If you want music, add a track from the YouTube Audio Library and check its license.
