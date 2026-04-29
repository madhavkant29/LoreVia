from io import BytesIO

from PIL import Image, ImageDraw

from app.utils.cover_processor import detect_border_region, process_cover, sample_edge_colors


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_detect_border_region_trims_plain_border():
    image = Image.new("RGB", (160, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 24, 144, 196), fill=(40, 70, 110))

    x, y, width, height = detect_border_region(image)

    assert x > 0
    assert y > 0
    assert width < 160
    assert height < 220


def test_sample_edge_colors_returns_hex_values():
    image = Image.new("RGB", (120, 160), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 12, 108, 148), fill=(31, 51, 91))

    colors = sample_edge_colors(image, (12, 12, 96, 136))

    assert set(colors) == {"top", "bottom", "left", "right", "dominant"}
    for value in colors.values():
        assert value.startswith("#")
        assert len(value) == 7


def test_process_cover_crops_and_returns_metadata():
    image = Image.new("RGBA", (180, 240), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 30, 160, 210), fill=(70, 30, 120, 255))

    processed = process_cover(_png_bytes(image))

    assert processed.mime_type == "image/png"
    assert processed.crop_bounds["width"] < 180
    assert processed.crop_bounds["height"] < 240
    assert processed.edge_colors["dominant"].startswith("#")
    assert processed.image_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_process_cover_ignores_transparent_edges():
    image = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 104, 104), fill=(200, 80, 40, 255))

    processed = process_cover(_png_bytes(image))

    assert processed.edge_colors["dominant"].startswith("#")
