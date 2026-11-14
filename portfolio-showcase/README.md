# LoreVia portfolio media

The technical walkthrough is a **4:35 narrated MP4** at `videos/lorevia-technical-walkthrough.mp4` (1920×1080, 30 fps, H.264/AAC). Its storyboard, narration, SRT subtitles, editable SVG diagrams, PNG diagram exports, screenshot copies, and GitHub-safe previews live beside it. The MP4 and raw WAV recording are intentionally ignored by Git; the previews and source assets can be committed.

## Rebuild

On Windows with Python 3.12, Pillow, PowerShell 7, System.Speech, and FFmpeg on `PATH`:

```powershell
python portfolio-showcase/render_walkthrough.py
python portfolio-showcase/make_previews.py
```

`render_walkthrough.py` builds temporary slide frames outside the checkout and removes them after encoding. `record_narration.ps1` generates sentence-level WAV files so `subtitles.srt` is timed to the synthesized narration. The render uses transitions and five sequential highlights for the upload slide. Those highlights illustrate the implementation; they are not live telemetry.

## Source and privacy

- Screenshots are copied from `frontend/public/landing/`, which depicts the actual UI with synthetic demo content. No customer manuscript, user account, secret, or production dashboard is shown.
- Diagram SVG and PNG are generated together from the node and edge definitions in `render_walkthrough.py`; their technical claims are mapped in [EVIDENCE.md](EVIDENCE.md).
- The video uses the real `frontend/public/logoandtext.png` asset.
- The memory discussion uses historical **local Docker** verification from `ops/production-memory-audit.md`. It does not state a production memory gain.

## Publishing step

The technical walkthrough MP4 has no verified public URL. Upload it as a GitHub Release asset, or to another explicitly authorized video host, then replace the technical preview target with the verified asset URL. Do not commit the technical MP4 into normal Git history. If the repository is private, a private Release asset and README will not be visible to unauthenticated recruiters; verify visibility and decide on a public-safe destination before publishing.

## Live product demonstration

The updated **6:02 product demonstration** uses an original sample manuscript and verified live captures. [Watch the full MP4](videos/lorevia-product-demo.mp4), committed on the `author` branch.
