"""Generates synthetic jewelry images with a known gem count, so the
evaluation harness has ground truth it can trust completely.

Each image is a ring-like band with N small filled circles ("gems") drawn
at random positions, plus optional "decoy" highlight circles that simulate
specular reflections on real metal -- these have no gem color at all, but
Hough circle detection reacts to edges, not color, so they can still get
counted as false-positive gems. Run:

    python scripts/generate_images.py
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "images"

IMAGE_SIZE = (400, 300)
BAND_COLOR = (200, 170, 60)     # gold-ish band
GEM_COLOR = (80, 160, 230)      # blue "gems" for strong contrast against the band
HIGHLIGHT_COLOR = (250, 245, 225)  # near-white specular highlight, no gem color at all
BACKGROUND_COLOR = (245, 245, 245)

# (filename, true_gem_count, seed, decoy_highlight_count)
# decoy_highlight_count simulates reflections/glare on a real photo -- they
# are not gems and should NOT be counted, but a classical edge-based
# detector doesn't know that.
CASES = [
    ("synthetic_ring_01.png", 3, 1, 0),
    ("synthetic_ring_02.png", 5, 2, 0),
    ("synthetic_ring_03.png", 7, 3, 0),
    ("synthetic_ring_04.png", 0, 4, 0),
    ("synthetic_ring_05.png", 12, 5, 0),
    ("synthetic_ring_06_plain.png", 0, 6, 0),        # negative control: truly plain band
    ("synthetic_ring_07_reflective.png", 0, 7, 6),    # 0 real gems, 6 decoy reflections
    ("synthetic_ring_08_mixed.png", 4, 8, 4),         # 4 real gems + 4 decoy reflections
]


def draw_ring_with_gems(gem_count: int, seed: int, decoy_highlight_count: int = 0) -> Image.Image:
    random.seed(seed)
    img = Image.new("RGB", IMAGE_SIZE, BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    band_box = (100, 120, 300, 180)
    draw.rounded_rectangle(band_box, radius=30, fill=BAND_COLOR)

    def place_circles(count: int, color: tuple[int, int, int], radius: int) -> None:
        placed = 0
        attempts = 0
        while placed < count and attempts < 200:
            attempts += 1
            x = random.randint(band_box[0] + radius, band_box[2] - radius)
            y = random.randint(band_box[1] + radius, band_box[3] - radius)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
            placed += 1

    place_circles(gem_count, GEM_COLOR, radius=10)
    place_circles(decoy_highlight_count, HIGHLIGHT_COLOR, radius=6)

    return img


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename, gem_count, seed, decoy_count in CASES:
        img = draw_ring_with_gems(gem_count, seed, decoy_count)
        out_path = OUTPUT_DIR / filename
        img.save(out_path)
        print(f"wrote {out_path} (true_gem_count={gem_count}, decoys={decoy_count})")


if __name__ == "__main__":
    main()
