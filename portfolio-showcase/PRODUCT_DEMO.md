# LoreVia product demonstration

The finished video is [`videos/lorevia-product-demo.mp4`](videos/lorevia-product-demo.mp4). It uses an original, six-chapter manuscript in [`recording/the-lantern-ledger.txt`](recording/the-lantern-ledger.txt), genuine captures of the authenticated LoreVia website, a short browser recording, and generated English narration. The 1920×1080 presentation is designed for portfolio use after the hosted service is unavailable.

## Verified product behavior

- Import recognized six named chapters plus opening material. The project reported seven indexed sections and progressed from readable text to story extraction.
- The Character Bible showed Talia Venn, alias Talia, mentions, and a profile summary. Three profile evidence batches were reported as unverified, so profile detail was incomplete.
- The relationship graph showed two characters and zero extracted connections for this sample. The video does not depict invented edges.
- Timeline and plot-thread views showed chapter spans, story events, open threads, and chapter links. Plot-thread chapter links are navigation references rather than quoted passage evidence.
- The recommended continuity scan ran against the sample and surfaced a possible brass-key ownership conflict. The source passage explicitly says Talia moved the key from a scarf to a tin box. The video treats the result as a false positive that requires author review.
- A deliberate green/blue eye-color contradiction was present in the original manuscript, but this run did not identify it as a finding. The advisor also failed to locate those descriptions. The screenshots of both passages are included as a transparent limitation.
- Manuscript search returned a ranked match for “green eyes” in the correct story chapter. Its UI describes results as top matches, not every occurrence.

No customer manuscript, authentication token, password, or other user's project was used in the public-facing captures. The sample project was created privately in the account authorized for this session. All screenshots were inspected before inclusion.

## Contents

- `videos/lorevia-product-demo.mp4`: final H.264 video with AAC narration.
- `screenshots/`: genuine screen captures and `video-thumbnail.png`.
- `screenshots/manuscript-upload.png`: the signed-in upload dialog, cropped to the product control so other projects and account details are excluded.
- `recording/the-lantern-ledger.txt`: original sample manuscript.
- `recording/chapter-reading.mp4`: short desktop capture of the real manuscript reading surface, inserted into the video.
- `recording/audio/`: narration segments and assembled WAV.
- `scripts/narration.md`: spoken script (941 words).
- `scripts/narration.srt`: timestamped subtitles.
- `scripts/storyboard.md` and `scripts/storyboard.json`: timestamped visual sequence.
- `scripts/synthesize.ps1` and `scripts/render_demo.py`: reproducible audio and video production.

## Reproduce the render

On Windows, install Python with Pillow and FFmpeg on `PATH`. From the repository root:

```powershell
& .\portfolio-showcase\scripts\synthesize.ps1 -Rate 0
python .\portfolio-showcase\scripts\render_demo.py
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of json .\portfolio-showcase\videos\lorevia-product-demo.mp4
```

The render script reads the checked screenshot captures and the existing browser recording. To recapture the live UI, sign into an authorized LoreVia account in a visible browser, import `recording/the-lantern-ledger.txt` as a private project, and wait for extraction to finish. Use the project's Chapters, Character Bible, Relationships, Timeline, Plot Threads, Story Advisor, and Search pages. Capture only the project view. This session's Windows desktop was 2560×1600 with the browser in the right panel; screenshots used:

```powershell
ffmpeg -f gdigrab -offset_x 1224 -offset_y 320 -video_size 1320x743 -framerate 1 -i desktop -frames:v 1 -vf scale=1920:1080 screenshot.png
```

The crop coordinates depend on window placement. Check a probe frame before recording and adjust them so no account or unrelated desktop content is visible. The video should be updated if a new run produces materially different findings.

The import segment shows a genuine capture of the signed-in upload dialog followed by the sample project's post-import processing and chapter screens. The dialog capture shows the source selector and supported formats; it was cropped to exclude other projects and account details. No replacement upload screen was fabricated.

## Editorial standard

The project demonstrates live application behavior and the limits of one run. A model-generated warning is a review candidate. The author or reviewer should read the cited passage before deciding whether to revise the manuscript. The untouched original sample makes the demonstrated key transfer and missed eye-color conflict reproducible.
