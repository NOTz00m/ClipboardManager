"""Generate the Qt PNG and multi-resolution Windows ICO app assets."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SCALE = 4
SIZE = 512


def s(value: int) -> int:
    return value * SCALE


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(tuple(s(value) for value in box), radius=s(radius), fill=fill)


def build_icon() -> Image.Image:
    canvas_size = SIZE * SCALE
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # Gradient-filled full-canvas squircle.
    gradient = Image.new("RGBA", image.size)
    pixels = gradient.load()
    start = (8, 123, 234)
    end = (91, 53, 213)
    for y in range(canvas_size):
        ratio = y / max(1, canvas_size - 1)
        color = tuple(round(start[i] * (1 - ratio) + end[i] * ratio) for i in range(3)) + (255,)
        for x in range(canvas_size):
            pixels[x, y] = color
    mask = Image.new("L", image.size, 0)
    rounded(ImageDraw.Draw(mask), (14, 14, 498, 498), 112, 255)
    image.alpha_composite(Image.composite(gradient, Image.new("RGBA", image.size), mask))

    draw = ImageDraw.Draw(image)
    rounded(draw, (129, 111, 399, 431), 42, (10, 44, 103, 62))
    rounded(draw, (113, 95, 383, 415), 42, (248, 251, 255, 255))
    rounded(draw, (185, 62, 311, 144), 30, (10, 44, 103, 255))
    rounded(draw, (218, 88, 278, 106), 9, (142, 217, 255, 255))
    rounded(draw, (164, 181, 333, 203), 11, (169, 197, 232, 255))
    rounded(draw, (164, 231, 290, 253), 11, (169, 197, 232, 255))

    # A bold check mark stays readable down to the 16px tray rendition.
    points = [(173, 324), (219, 370), (322, 259)]
    draw.line([(s(x), s(y)) for x, y in points], fill=(38, 211, 209, 255), width=s(34), joint="curve")
    for x, y in points:
        draw.ellipse((s(x - 17), s(y - 17), s(x + 17), s(y + 17)), fill=(38, 211, 209, 255))

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main():
    icon = build_icon()
    icon.save(ROOT / "clipboard.png", optimize=True)
    icon.save(
        ROOT / "clipboard_manager.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
