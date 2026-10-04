"""Build every brand asset from the transparent Otter Data logo.

Usage: python -m scripts.build_brand_assets (needs Pillow and numpy).
Coordinates match assets/otter-data-logo-source.webp (1536x1024); adjust them for a new layout.
"""

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "otter-data-logo-source.webp"
OUT = ROOT / "frontend" / "assets"

full = np.asarray(Image.open(SRC).convert("RGBA")).astype(np.float32)
H, W = full.shape[:2]
yy, xx = np.mgrid[0:H, 0:W]
r, g, b, a = (full[..., i] for i in range(4))
blueish = b > r + 25
brownish = r > b + 25
wave = (b > r + 40) & (
    b > 110
)  # light teal of the waves, not the dark navy ink of eyes and whiskers
TEXT_TOP = 736  # first row of the lettering
SPLIT_X = 888  # "Otter" | "Data"


def crop_to_alpha(rgba: np.ndarray, pad: int = 8) -> np.ndarray:
    ys, xs = np.where(rgba[..., 3] > 12)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, rgba.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, rgba.shape[1])
    return rgba[y0:y1, x0:x1]


def save(rgba: np.ndarray, name: str, width: int) -> Image.Image:
    image = Image.fromarray(rgba.clip(0, 255).astype(np.uint8), "RGBA")
    height = round(image.height * width / image.width)
    image = image.resize((width, height), Image.LANCZOS)
    image.save(OUT / name, "WEBP", quality=92, method=6)
    print(name, image.size)
    return image


# 1. Full logo, light theme: as supplied.
light = save(crop_to_alpha(full), "logo.webp", 640)

# 2. Night edition: "Otter" in cream, "Data" in a lighter blue, whiskers over the background in
#    cream. Alpha is untouched, so anti-aliased edges stay clean.
dark = full.copy()
otter_text = (yy >= 700) & (xx < SPLIT_X) & brownish  # the "O" rises above the other letters
data_text = (yy >= TEXT_TOP) & (xx >= SPLIT_X) & blueish
whiskers = (xx >= 1012) & (yy >= 175) & (yy <= 305) & (np.maximum(np.maximum(r, g), b) < 120)
dark[otter_text, :3] = (236, 226, 208)
dark[data_text, :3] = (128, 182, 194)
dark[whiskers, :3] = (236, 226, 208)
save(crop_to_alpha(dark), "logo-dark.webp", 640)

# 3. Mascot without lettering (welcome screen, desktop splash): keep the waves' tail, drop text.
mascot = full.copy()
drop = ((yy >= 700) & brownish) | ((yy >= TEXT_TOP) & (xx >= SPLIT_X)) | (yy >= 742)
mascot[drop, 3] = 0
save(crop_to_alpha(mascot), "otter-mascot.webp", 520)

# 4. Head portrait (answer avatar, mobile top bar, favicon, desktop icon).
head = full[95:615, 590:1110].copy()  # square around the head, ear and whiskers
head[wave[95:615, 590:1110], 3] = 0  # no wave fragments in the portrait
face = Image.fromarray(head.clip(0, 255).astype(np.uint8), "RGBA")
face.resize((160, 160), Image.LANCZOS).save(OUT / "otter-face.webp", "WEBP", quality=92, method=6)
icon = full[95:615, 590:1110].copy()
icon[wave[95:615, 590:1110], 3] = 0
icon_source = Image.fromarray(icon.clip(0, 255).astype(np.uint8), "RGBA")
side = max(icon_source.size)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(icon_source, ((side - icon_source.width) // 2, (side - icon_source.height) // 2))
square.resize((64, 64), Image.LANCZOS).save(OUT / "favicon.png")
square.resize((256, 256), Image.LANCZOS).save(
    OUT / "otter.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("face + icons ok")
