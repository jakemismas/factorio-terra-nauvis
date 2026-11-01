#!/usr/bin/env python3
"""Write terra-nauvis/graphics/frozen-ground.png, the art of the mod's one tile (config.lua tiles.frozen).

  python tools/build_frozen_tile.py

Procedural and seeded, so a rerun gives the same file. The sheet has the layout of the base game's tile sheets at half
their size: 16 variants of 1, 2 and 4 tiles, 32 px a tile. Each variant fades to the mean colour at its edges, so any
variant meets any other without a seam.
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

OUT = Path(__file__).resolve().parents[1] / "terra-nauvis" / "graphics" / "frozen-ground.png"
TILE = 32
ROWS = ((1, 0), (2, 64), (4, 160))
WIDE, HIGH = TILE * 4 * 16, 288
MEAN = np.array([212.0, 217.0, 225.0])
BLUE = np.array([-5.0, -2.0, 3.0])


def variant(rng, size):
    field = sum(w * ndimage.gaussian_filter(rng.standard_normal((size, size)), s, mode="wrap") * s
                for s, w in ((1.0, 0.8), (3.0, 1.2), (9.0, 1.6)))
    field = field / field.std()
    edge = np.minimum.outer(np.minimum(np.arange(size), size - 1 - np.arange(size)),
                            np.minimum(np.arange(size), size - 1 - np.arange(size)))
    fade = np.clip(edge / 6.0, 0, 1)[..., None]
    shade = field[..., None] * fade
    return MEAN + shade * 5.0 + np.clip(-shade, 0, None) * BLUE


def main():
    rng = np.random.default_rng(7608)
    sheet = np.zeros((HIGH, WIDE, 3))
    sheet[:] = MEAN
    for tiles, y in ROWS:
        size = TILE * tiles
        for i in range(16):
            sheet[y:y + size, i * size:(i + 1) * size] = variant(rng, size)
    OUT.parent.mkdir(exist_ok=True)
    Image.fromarray(np.clip(np.rint(sheet), 0, 255).astype(np.uint8)).save(OUT, optimize=True)
    print("RESULT ok", OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()
