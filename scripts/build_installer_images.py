"""Draw the Windows installer's wizard images from the app's logo and colors.

Usage: python -m scripts.build_installer_images (needs Pillow; Windows, for the Georgia font).
Writes packaging/images/: the tall image of the welcome and finish pages and the small image of
the inner pages, in light and dark versions and in several sizes so Inno Setup can pick the one
that matches the screen's DPI.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend" / "assets"
OUT = ROOT / "packaging" / "images"
FONT = Path("C:/Windows/Fonts/georgiai.ttf")

# Same tokens as frontend/styles.css (--paper-2, --ink-2, --action) for each theme.
THEMES = {
    "light": {"panel": "#EEE5D4", "text": "#5A4E44", "accent": "#9A5636", "logo": "logo.webp"},
    "dark": {"panel": "#1A2225", "text": "#C9BEAC", "accent": "#BE8264", "logo": "logo-dark.webp"},
}
# Base size of Inno Setup's large wizard image (164x314) and the DPI scales it offers.
SCALES = (1.0, 1.5, 2.0, 2.5)


def tall_image(theme: dict, scale: float) -> Image.Image:
    width, height = round(164 * scale), round(314 * scale)
    image = Image.new("RGB", (width, height), theme["panel"])
    draw = ImageDraw.Draw(image)
    logo = Image.open(ASSETS / theme["logo"]).convert("RGBA")
    logo_width = round(width * 0.82)
    logo = logo.resize((logo_width, round(logo.height * logo_width / logo.width)), Image.LANCZOS)
    top = round(height * 0.22)
    image.paste(logo, ((width - logo_width) // 2, top), logo)
    font = ImageFont.truetype(str(FONT), round(14 * scale))
    tagline = "Ask your data."
    text_top = top + logo.height + round(14 * scale)
    text_width = draw.textlength(tagline, font=font)
    draw.text(((width - text_width) / 2, text_top), tagline, font=font, fill=theme["text"])
    # A short terracotta rule under the tagline and a hairline along the page edge.
    rule = round(28 * scale)
    y = text_top + round(26 * scale)
    draw.line(
        [((width - rule) / 2, y), ((width + rule) / 2, y)],
        fill=theme["accent"],
        width=max(1, round(2 * scale)),
    )
    draw.line(
        [(width - 1, 0), (width - 1, height)], fill=theme["accent"], width=max(1, round(scale))
    )
    return image


def small_image(scale: float) -> Image.Image:
    # Transparent margin: Inno Setup draws this image flush with the window's top-right corner.
    size = round(55 * scale)
    face_size = round(size * 0.78)
    face = Image.open(ASSETS / "otter-face.webp").convert("RGBA")
    face = face.resize((face_size, face_size), Image.LANCZOS)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    image.paste(face, ((size - face_size) // 2, (size - face_size) // 2), face)
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        for scale in SCALES:
            path = OUT / f"wizard-{name}-{round(scale * 100)}.png"
            tall_image(theme, scale).save(path, optimize=True)
            print(path.name)
    for scale in SCALES:
        path = OUT / f"wizard-small-{round(scale * 100)}.png"
        small_image(scale).save(path, optimize=True)
        print(path.name)


if __name__ == "__main__":
    main()
