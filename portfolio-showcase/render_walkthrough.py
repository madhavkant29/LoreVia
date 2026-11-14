"""Render editable architecture diagrams, synthetic UI slides, captions, and MP4.

Requires Python 3.12, Pillow, FFmpeg, and Windows System.Speech for narration.
Run from any directory: python portfolio-showcase/render_walkthrough.py
"""

from __future__ import annotations

import html
import json
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
STORY = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
NAVY = "#0b1021"
PANEL = "#17223b"
PANEL_2 = "#20314d"
WHITE = "#f7f9ff"
MUTED = "#aebbd3"
TEAL = "#5de3c1"
VIOLET = "#b8a3ff"
GOLD = "#f6c96b"
W, H = 1920, 1080
FONT_REG = Path("C:/Windows/Fonts/segoeui.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/segoeuib.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REG), size)


def node(key: str, x: int, y: int, title: str, detail: str, w: int = 235, h: int = 108):
    return {"key": key, "x": x, "y": y, "w": w, "h": h, "title": title, "detail": detail}


DIAGRAMS = {
    "system": {
        "title": "System architecture",
        "nodes": [
            node("user", 35, 300, "Author", "Browser"),
            node("next", 315, 300, "Next.js 15", "App Router / Vercel", 255),
            node("api", 640, 300, "FastAPI", "Routes → services", 250),
            node("pg", 965, 88, "PostgreSQL", "pgvector + task state", 265),
            node("redis", 965, 300, "Redis", "Celery broker", 265),
            node("store", 965, 512, "Object storage", "R2-compatible / local", 265),
            node("workers", 1325, 300, "Celery workers", "Five specialized roles", 245),
        ],
        "edges": [("user", "next"), ("next", "api"), ("api", "pg"), ("api", "redis"), ("api", "store"), ("redis", "workers"), ("workers", "pg"), ("workers", "store")],
    },
    "ingestion": {
        "title": "Manuscript ingestion and task dispatch",
        "nodes": [
            node("upload", 32, 100, "Upload request", "Bounded file read", 240),
            node("validate", 330, 100, "Validate + preview", "Signature / structure", 245),
            node("store", 635, 100, "Object storage", "Source manuscript", 245),
            node("book", 635, 430, "PostgreSQL", "Book + processing run", 245),
            node("outbox", 950, 430, "Dispatch outbox", "Durable execution", 245),
            node("broker", 1270, 430, "Redis broker", "Celery message", 245),
            node("worker", 950, 100, "Extraction worker", "Parse + chapter jobs", 245),
            node("chapters", 1270, 100, "Chapters + chunks", "Persisted results", 245),
        ],
        "edges": [("upload", "validate"), ("validate", "store"), ("validate", "book"), ("book", "outbox"), ("outbox", "broker"), ("broker", "worker"), ("store", "worker"), ("worker", "chapters")],
    },
    "workers": {
        "title": "Celery queue routing",
        "nodes": [
            node("beat", 60, 55, "Celery Beat", "Schedules maintenance", 255, 94),
            node("redis", 60, 306, "Redis broker", "Message transport", 255, 104),
            node("eq", 420, 38, "extraction", "+ extraction_priority", 300, 92),
            node("aq", 420, 173, "analysis", "+ analysis_priority", 300, 92),
            node("bq", 420, 308, "embedding", "Vector jobs", 300, 92),
            node("iq", 420, 443, "intelligence", "Advisor + voice", 300, 92),
            node("mq", 420, 578, "maintenance", "Recovery + exports", 300, 92),
            node("ew", 1000, 38, "Extraction worker", "Parser + chapter tasks", 400, 92),
            node("aw", 1000, 173, "Analysis worker", "Chapter analysis", 400, 92),
            node("bw", 1000, 308, "Embedding worker", "OpenAI embeddings", 400, 92),
            node("iw", 1000, 443, "Intelligence worker", "Advisor / voice / repair", 400, 92),
            node("mw", 1000, 578, "Maintenance worker", "Outbox / scheduled jobs", 400, 92),
        ],
        "edges": [("beat", "redis"), ("redis", "eq"), ("redis", "aq"), ("redis", "bq"), ("redis", "iq"), ("redis", "mq"), ("eq", "ew"), ("aq", "aw"), ("bq", "bw"), ("iq", "iw"), ("mq", "mw")],
    },
    "ai": {
        "title": "Extraction, embeddings, retrieval",
        "nodes": [
            node("source", 30, 310, "Manuscript", "Validated source", 230),
            node("parse", 330, 130, "Parser", "Chapters + chunks", 240),
            node("chars", 330, 490, "Character engine", "Candidates + identity", 240),
            node("embed", 650, 130, "Embeddings", "Tracked model calls", 240),
            node("db", 960, 130, "pgvector", "Book-scoped vectors", 240),
            node("search", 1270, 130, "Hybrid search", "Chapter boundary", 260),
            node("advisor", 1270, 490, "Advisor + checks", "Citations / evidence", 260),
        ],
        "edges": [("source", "parse"), ("source", "chars"), ("parse", "embed"), ("parse", "chars"), ("embed", "db"), ("db", "search"), ("search", "advisor"), ("chars", "advisor")],
    },
    "deployment": {
        "title": "Tracked deployment topology",
        "nodes": [
            node("browser", 20, 65, "Browser", "Author workspace", 240),
            node("vercel", 335, 65, "Vercel", "Next.js frontend", 240),
            node("cf", 650, 65, "Cloudflare", "API edge / DNS", 240),
            node("nginx", 965, 65, "Nginx", "Hetzner VPS", 240),
            node("api", 1280, 65, "FastAPI", "Gunicorn / Compose", 270),
            node("supabase", 335, 430, "Supabase Auth", "OAuth identity", 240),
            node("r2", 650, 430, "R2-compatible", "Object storage", 240),
            node("pg", 965, 430, "PostgreSQL", "pgvector database", 240),
            node("redis", 1280, 370, "Redis", "Broker / session data", 270),
            node("workers", 1280, 555, "Celery + Beat", "Five worker roles", 270),
        ],
        "edges": [("browser", "vercel"), ("vercel", "cf"), ("cf", "nginx"), ("nginx", "api"), ("api", "supabase"), ("api", "r2"), ("api", "pg"), ("api", "redis"), ("redis", "workers"), ("workers", "pg"), ("workers", "r2")],
    },
}


def endpoints(a: dict, b: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    ax, ay = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
    bx, by = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    dx, dy = bx - ax, by - ay
    if abs(dx) / max(a["w"], 1) > abs(dy) / max(a["h"], 1):
        sx = a["x"] + (a["w"] if dx >= 0 else 0)
        sy = ay
    else:
        sx = ax
        sy = a["y"] + (a["h"] if dy >= 0 else 0)
    if abs(dx) / max(b["w"], 1) > abs(dy) / max(b["h"], 1):
        ex = b["x"] + (0 if dx >= 0 else b["w"])
        ey = by
    else:
        ex = bx
        ey = b["y"] + (0 if dy >= 0 else b["h"])
    return (sx, sy), (ex, ey)


def arrow_points(start, end):
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    back = (end[0] - 14 * math.cos(angle), end[1] - 14 * math.sin(angle))
    return [end, (back[0] + 7 * math.sin(angle), back[1] - 7 * math.cos(angle)), (back[0] - 7 * math.sin(angle), back[1] + 7 * math.cos(angle))]


def draw_diagram(name: str) -> None:
    spec = DIAGRAMS[name]
    nodes = {n["key"]: n for n in spec["nodes"]}
    canvas = Image.new("RGB", (1600, 720), NAVY)
    draw = ImageDraw.Draw(canvas)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="720" viewBox="0 0 1600 720">', f'<rect width="1600" height="720" fill="{NAVY}"/>']
    edges = spec["edges"]
    if name == "workers":
        edges = [(src, dst) for src, dst in edges if src != "redis"]
        bus = [(315, 358), (365, 358), (365, 84), (365, 624)]
        draw.line(bus[:2], fill=TEAL, width=4)
        draw.line(bus[1:3], fill=TEAL, width=4)
        draw.line(bus[2:4], fill=TEAL, width=4)
        svg.append(f'<path d="M315 358 H365 V84 V624" fill="none" stroke="{TEAL}" stroke-width="4"/>')
        for y in (84, 219, 354, 489, 624):
            draw.line(((365, y), (420, y)), fill=TEAL, width=4)
            draw.polygon(arrow_points((365, y), (420, y)), fill=TEAL)
            svg.append(f'<line x1="365" y1="{y}" x2="420" y2="{y}" stroke="{TEAL}" stroke-width="4"/>')
            svg.append('<polygon points="' + ' '.join(f'{x:.1f},{py:.1f}' for x, py in arrow_points((365, y), (420, y))) + f'" fill="{TEAL}"/>')
    for src, dst in edges:
        start, end = endpoints(nodes[src], nodes[dst])
        draw.line([start, end], fill=TEAL, width=4)
        pts = arrow_points(start, end)
        draw.polygon(pts, fill=TEAL)
        svg.append(f'<line x1="{start[0]:.1f}" y1="{start[1]:.1f}" x2="{end[0]:.1f}" y2="{end[1]:.1f}" stroke="{TEAL}" stroke-width="4"/>')
        svg.append('<polygon points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts) + f'" fill="{TEAL}"/>')
    for n in spec["nodes"]:
        x, y, w, h = n["x"], n["y"], n["w"], n["h"]
        draw.rounded_rectangle((x, y, x + w, y + h), radius=17, fill=PANEL, outline=VIOLET, width=2)
        title_size = 28
        while draw.textbbox((0, 0), n["title"], font=font(title_size, True))[2] > w - 38:
            title_size -= 1
        draw.text((x + 19, y + 19), n["title"], font=font(title_size, True), fill=WHITE)
        draw.text((x + 19, y + 60), n["detail"], font=font(18), fill=MUTED)
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="17" fill="{PANEL}" stroke="{VIOLET}" stroke-width="2"/>')
        svg.append(f'<text x="{x+19}" y="{y+48}" font-family="Segoe UI,Arial" font-size="{title_size}" font-weight="700" fill="{WHITE}">{html.escape(n["title"])}</text>')
        svg.append(f'<text x="{x+19}" y="{y+83}" font-family="Segoe UI,Arial" font-size="18" fill="{MUTED}">{html.escape(n["detail"])}</text>')
    svg.append('</svg>')
    out = ROOT / "diagrams"
    out.mkdir(parents=True, exist_ok=True)
    canvas.save(out / f"{name}.png", optimize=True)
    (out / f"{name}.svg").write_text("\n".join(svg), encoding="utf-8")


def fit_image(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as source:
        return ImageOps.contain(source.convert("RGB"), size, Image.Resampling.LANCZOS)


def text_lines(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, width: int, size: int, color: str = WHITE, leading: int | None = None) -> int:
    f = font(size)
    line = ""
    step = leading or int(size * 1.42)
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textbbox((0, 0), trial, font=f)[2] > width and line:
            draw.text((x, y), line, font=f, fill=color)
            y += step
            line = word
        else:
            line = trial
    if line:
        draw.text((x, y), line, font=f, fill=color)
        y += step
    return y


def card(draw, xy, title, body, accent=TEAL):
    x, y, w, h = xy
    draw.rounded_rectangle((x, y, x + w, y + h), radius=24, fill=PANEL, outline=accent, width=2)
    draw.text((x + 28, y + 23), title, font=font(29, True), fill=WHITE)
    text_lines(draw, body, x + 28, y + 69, w - 54, 22, MUTED)


def screenshot(canvas: Image.Image, name: str, box: tuple[int, int, int, int]) -> None:
    x, y, w, h = box
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((x - 7, y - 7, x + w + 7, y + h + 7), radius=18, fill=PANEL_2)
    picture = fit_image(ROOT / "screenshots" / name, (w, h))
    canvas.paste(picture, (x + (w - picture.width) // 2, y + (h - picture.height) // 2))


def slide(index: int, scene: dict, stage: int | None = None) -> Image.Image:
    canvas = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, W, 12), fill=TEAL)
    d.text((94, 48), f"LOREVIA / ARCHITECTURE  •  {index+1:02d} / 10", font=font(22, True), fill=TEAL)
    d.text((94, 92), scene["title"], font=font(62, True), fill=WHITE)
    logo = fit_image(REPO / "frontend/public/logoandtext.png", (225, 70))
    d.rounded_rectangle((1590, 38, 1845, 124), radius=15, fill="#000000")
    canvas.paste(logo, (1717 - logo.width // 2, 81 - logo.height // 2))
    visual = scene["visual"]
    if visual in {"system", "ingestion", "workers", "deployment"}:
        diagram = fit_image(ROOT / "diagrams" / f"{visual}.png", (1750, 788))
        canvas.paste(diagram, ((W - diagram.width) // 2, 175))
        if visual == "ingestion":
            steps = ["Validate", "Store", "Commit", "Dispatch", "Process"]
            for j, label in enumerate(steps):
                fill = TEAL if stage == j else PANEL_2
                d.rounded_rectangle((105 + j * 345, 930, 420 + j * 345, 984), radius=16, fill=fill)
                d.text((128 + j * 345, 940), f"{j+1:02d}  {label}", font=font(25, True), fill=NAVY if stage == j else WHITE)
            d.text((102, 897), "Illustrative pipeline animation • based on code, not live telemetry", font=font(20), fill=MUTED)
    elif visual == "frontend":
        screenshot(canvas, "manuscript-analysis.webp", (95, 218, 830, 525))
        screenshot(canvas, "notes-workspace.webp", (995, 218, 830, 525))
        card(d, (95, 770, 1730, 155), "App Router + client state", "React 19 • TanStack Query for server state • Zustand for selected UI state • credentialed Axios through /api/v1")
    elif visual == "api":
        items = [
            ("01  Request boundary", "FastAPI dependencies resolve the caller; Pydantic validates input."),
            ("02  Application layer", "Services coordinate storage, transactions, and dispatch."),
            ("03  Data boundary", "Async SQLAlchemy sessions write PostgreSQL; Alembic versions schema."),
        ]
        for j, (head, body) in enumerate(items):
            card(d, (95, 205 + j * 235, 825, 195), head, body, [TEAL, VIOLET, GOLD][j])
        card(d, (975, 205, 850, 650), "Real upload transaction", "backend/app/services/book_upload_service.py", VIOLET)
        code = ["book = Book(status=\"pending\", ...)", "processing_run = await get_or_create_processing_run(...)\n", "await ensure_task_execution(...)", "await db.commit()", "await dispatch_pending_extraction_tasks(db)"]
        y = 355
        for line in code:
            d.text((1035, y), line.strip(), font=font(25), fill=TEAL if "commit" in line or "dispatch" in line else WHITE)
            y += 72
    elif visual == "extraction":
        ai = fit_image(ROOT / "diagrams/ai.png", (1760, 730))
        canvas.paste(ai, ((W - ai.width) // 2, 180))
        d.text((105, 928), "Chapter records, chunks, character evidence, analysis, and embeddings are persisted for later views.", font=font(26), fill=MUTED)
    elif visual == "retrieval":
        screenshot(canvas, "manuscript-analysis-with-advisor.webp", (98, 238, 865, 515))
        card(d, (1008, 238, 810, 515), "Query → evidence", "Embed question → book and chapter filtered pgvector search → optional lexical rerank → advisor context → cited answer", VIOLET)
        card(d, (98, 790, 1720, 145), "Boundary", "Source text and model output are untrusted. The displayed citations refer to retrieved passages and chapter references.", TEAL)
    elif visual == "recovery":
        items = [
            ("Problem", "A publish or worker can fail after durable work is recorded."),
            ("Root cause", "Database and broker are separate failure domains."),
            ("Solution", "TaskExecution identity + dispatch outbox + locked claims."),
            ("Verification", "Local ingestion and live worker tests; maintenance reconciliation."),
            ("Tradeoff", "More control-plane code and explicit terminal-state checks."),
        ]
        for j, (head, body) in enumerate(items):
            x = 105 + (j % 3) * 585
            y = 215 + (j // 3) * 315
            card(d, (x, y, 540, 260), head, body, [TEAL, VIOLET, GOLD][j % 3])
    elif visual == "health":
        card(d, (100, 210, 790, 620), "Before → after", "All task modules loaded in each worker and probe. Role-specific task imports and a minimal Celery health client now preserve exact-worker responsiveness checks.", TEAL)
        card(d, (940, 210, 880, 620), "Health probe excerpt", "backend/app/workers/healthcheck.py", VIOLET)
        lines = ["app = Celery(\"lorevia\", broker=broker_url)", "reply = app.control.inspect(", "    destination=[destination],", "    timeout=PING_TIMEOUT_SECONDS", ").ping()", "", "# exact destination must return pong"]
        for j, line in enumerate(lines):
            d.text((990, 400 + j * 46), line, font=font(26), fill=TEAL if "destination" in line or "ping" in line else WHITE)
        d.text((104, 900), "Local Docker verification; no measured VPS before/after memory claim.", font=font(27, True), fill=GOLD)
    d.line((95, 1010, 1825, 1010), fill=PANEL_2, width=2)
    d.text((95, 1020), "Architecture reconstructed from repository source • synthetic UI captures", font=font(21), fill=MUTED)
    return canvas


def prepare_screenshots() -> None:
    src = REPO / "frontend/public/landing"
    dst = ROOT / "screenshots"
    dst.mkdir(parents=True, exist_ok=True)
    for name in ["manuscript-analysis", "notes-workspace", "character-continuity", "relationship-graph", "editorial-review-2", "manuscript-analysis-with-advisor"]:
        shutil.copyfile(src / f"{name}.webp", dst / f"{name}.webp")


def srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, rest = divmod(milliseconds, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def audio_and_captions() -> None:
    import re

    sentence_dir = ROOT / "audio/sentences"
    sentences = [s.strip() for scene in STORY["scenes"] for s in re.split(r"(?<=[.!?])\s+", scene["narration"]) if s.strip()]
    first = wave.open(str(sentence_dir / "000.wav"), "rb")
    params = first.getparams()
    first.close()
    cursor = 0.0
    captions = []
    all_frames = []
    sentence_index = 0
    for scene in STORY["scenes"]:
        scene_start = cursor
        scene_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", scene["narration"]) if s.strip()]
        for sentence in scene_sentences:
            with wave.open(str(sentence_dir / f"{sentence_index:03d}.wav"), "rb") as source:
                if source.getparams()[:3] != params[:3]:
                    raise RuntimeError("Narration WAV formats differ")
                frames = source.readframes(source.getnframes())
            start = cursor
            duration = len(frames) / params.nchannels / params.sampwidth / params.framerate
            cursor += duration
            all_frames.append(frames)
            captions.append((start, cursor, sentence))
            gap = 0.22
            all_frames.append(b"\0" * round(gap * params.framerate) * params.nchannels * params.sampwidth)
            cursor += gap
            sentence_index += 1
        target = scene_start + scene["duration"]
        if cursor > target + 0.01:
            raise RuntimeError(f"Narration exceeds scene {scene['title']}: {cursor - scene_start:.1f}s > {scene['duration']}s")
        pad = target - cursor
        all_frames.append(b"\0" * round(pad * params.framerate) * params.nchannels * params.sampwidth)
        cursor = target
    audio = ROOT / "audio/narration.wav"
    with wave.open(str(audio), "wb") as result:
        result.setparams(params)
        result.writeframes(b"".join(all_frames))
    (ROOT / "subtitles.srt").write_text("\n\n".join(f"{i+1}\n{srt_time(a)} --> {srt_time(b)}\n{text}" for i, (a, b, text) in enumerate(captions)) + "\n", encoding="utf-8")
    (ROOT / "narration.md").write_text("# Narration script\n\n" + "\n\n".join(f"## {scene['title']} ({scene['duration']}s)\n\n{scene['narration']}" for scene in STORY["scenes"]) + "\n", encoding="utf-8")


def render_video_in(assets: Path) -> None:
    slides = assets / "slides"
    transitions = assets / "transitions"
    slides.mkdir(parents=True, exist_ok=True)
    transitions.mkdir(parents=True, exist_ok=True)
    scene_images = []
    for i, scene in enumerate(STORY["scenes"]):
        if scene["visual"] == "ingestion":
            pictures = []
            for stage in range(5):
                p = slides / f"scene_{i:02d}_{stage}.png"
                slide(i, scene, stage).save(p, optimize=True)
                pictures.append(p)
        else:
            p = slides / f"scene_{i:02d}.png"
            slide(i, scene).save(p, optimize=True)
            pictures = [p]
        scene_images.append(pictures)
    entries = []
    for i, (scene, pictures) in enumerate(zip(STORY["scenes"], scene_images)):
        if len(pictures) == 1:
            entries.append((pictures[0], scene["duration"] - (0.4 if i < len(scene_images) - 1 else 0)))
        else:
            for p in pictures:
                entries.append((p, scene["duration"] / len(pictures) - (0.4 if p == pictures[-1] else 0)))
        if i < len(scene_images) - 1:
            with Image.open(pictures[-1]) as before, Image.open(scene_images[i + 1][0]) as after:
                for j in range(1, 13):
                    p = transitions / f"cross_{i:02d}_{j:02d}.png"
                    Image.blend(before, after, j / 13).save(p, optimize=True)
                    entries.append((p, 1 / 30))
    entries.append((scene_images[-1][-1], 1 / 30))
    timeline = assets / "timeline.txt"
    timeline.write_text("\n".join(f"file '{p.as_posix()}'\nduration {duration:.6f}" for p, duration in entries) + "\n", encoding="utf-8")
    output = ROOT / "videos/lorevia-technical-walkthrough.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(timeline), "-i", str(ROOT / "audio/narration.wav"), "-i", str(ROOT / "subtitles.srt"), "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0", "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-t", "275", "-movflags", "+faststart", str(output)], check=True)
    slide(0, STORY["scenes"][0]).resize((1280, 720), Image.Resampling.LANCZOS).save(ROOT / "technical-thumbnail.webp", quality=88)


def render_video() -> None:
    with tempfile.TemporaryDirectory(prefix="lorevia-walkthrough-") as build_dir:
        render_video_in(Path(build_dir))


def main() -> None:
    if sum(scene["duration"] for scene in STORY["scenes"]) != STORY["duration_seconds"]:
        raise RuntimeError("Storyboard duration mismatch")
    prepare_screenshots()
    for name in DIAGRAMS:
        draw_diagram(name)
    subprocess.run(["pwsh", "-NoProfile", "-File", str(ROOT / "record_narration.ps1"), "-Root", str(ROOT)], check=True)
    audio_and_captions()
    render_video()
    print(f"Rendered {ROOT / 'videos/lorevia-technical-walkthrough.mp4'}")


if __name__ == "__main__":
    main()
