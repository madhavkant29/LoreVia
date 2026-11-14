"""Validate the portfolio README, media, and editable diagram exports."""

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def main() -> None:
    storyboard = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
    assert sum(scene["duration"] for scene in storyboard["scenes"]) == 275
    assert len(storyboard["scenes"]) == 10

    readme = (REPO / "README.md").read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)]+)\)", readme)
    targets += re.findall(r'(?:src|href)="([^"]+)"', readme)
    missing = [target for target in targets if not target.startswith(("http:", "https:", "#")) and not (REPO / target).exists()]
    assert not missing, f"README targets missing: {missing}"

    for name in ("system", "ingestion", "workers", "ai", "deployment"):
        ET.parse(ROOT / "diagrams" / f"{name}.svg")
        with Image.open(ROOT / "diagrams" / f"{name}.png") as image:
            assert image.size == (1600, 720)

    for name in ("manuscript-analysis", "notes-workspace", "character-continuity", "relationship-graph", "editorial-review-2", "manuscript-analysis-with-advisor"):
        with Image.open(ROOT / "screenshots" / f"{name}.webp") as image:
            assert image.width >= 1200 and image.height >= 680

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-show_entries", "stream=codec_name,width,height,r_frame_rate", "-of", "json", str(ROOT / "videos/lorevia-technical-walkthrough.mp4")],
        capture_output=True,
        text=True,
        check=True,
    )
    media = json.loads(probe.stdout)
    assert 274.8 <= float(media["format"]["duration"]) <= 275.2
    video, audio, subtitles = media["streams"]
    assert video["codec_name"] == "h264"
    assert video["width"] == 1920 and video["height"] == 1080
    assert video["r_frame_rate"] == "30/1"
    assert audio["codec_name"] == "aac"
    assert subtitles["codec_name"] == "mov_text"
    assert (ROOT / "subtitles.srt").read_text(encoding="utf-8").count("-->") >= 35
    print("Portfolio assets and README links verified; video is 4:35 with H.264/AAC/subtitles.")


if __name__ == "__main__":
    main()
