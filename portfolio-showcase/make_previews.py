"""Build GitHub-safe animated previews and thumbnails from verified showcase assets."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from render_walkthrough import REPO, ROOT, STORY, slide


FONT = Path("C:/Windows/Fonts/segoeuib.ttf")
PRODUCT = [
    ("manuscript-analysis.webp", "Manuscript workspace"),
    ("character-continuity.webp", "Character intelligence"),
    ("relationship-graph.webp", "Relationship graph"),
    ("editorial-review-2.webp", "Continuity review"),
    ("manuscript-analysis-with-advisor.webp", "Evidence-backed answers"),
    ("notes-workspace.webp", "Author notes"),
]


def product_frame(name: str, title: str) -> Image.Image:
    image = Image.new("RGB", (1280, 720), "#0b1021")
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 1280, 9), fill="#5de3c1")
    d.text((48, 32), "LOREVIA  /  PRODUCT UI", font=ImageFont.truetype(str(FONT), 25), fill="#5de3c1")
    d.text((48, 79), title, font=ImageFont.truetype(str(FONT), 48), fill="#ffffff")
    with Image.open(ROOT / "screenshots" / name) as source:
        picture = ImageOps.contain(source.convert("RGB"), (1170, 520), Image.Resampling.LANCZOS)
    image.paste(picture, ((1280 - picture.width) // 2, 161 + (520 - picture.height) // 2))
    d.text((49, 686), "Screenshots use synthetic demo content", font=ImageFont.truetype(str(FONT), 18), fill="#aebbd3")
    return image


def gif(frames: list[Image.Image], path: Path, duration: int) -> None:
    small = [frame.resize((640, 360), Image.Resampling.LANCZOS).quantize(colors=128) for frame in frames]
    small[0].save(path, save_all=True, append_images=small[1:], duration=duration, loop=0, optimize=True)


def main() -> None:
    technical = [slide(i, STORY["scenes"][i]) for i in (0, 3, 4, 6, 9)]
    gif(technical, ROOT / "technical-preview.gif", 1500)
    product = [product_frame(*item) for item in PRODUCT]
    gif(product, ROOT / "product-preview.gif", 1400)
    product[0].save(ROOT / "product-thumbnail.webp", quality=88)


if __name__ == "__main__":
    main()
