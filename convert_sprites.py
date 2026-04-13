#!/usr/bin/env python3
"""
convert_sprites.py
==================
Converts generated pixel-art PNGs → 240×240 4-bit palette binary files
ready to be uploaded to the MicroPython ESP32 filesystem.

Output per image:
    <name>.bin  — raw 4-bit packed pixel data, 28800 bytes (240×240÷2)
    palette lines printed to stdout for pasting into themes.py

Usage:
    python3 convert_sprites.py
"""

from PIL import Image
import os, struct

SPRITE_DIR  = "/home/matt/.gemini/antigravity/brain/384bc580-247b-449f-9ff7-6888c641495e"
OUT_DIR     = "/home/matt/Documents/aiapps/cyd-fun-clock/sprites"
SIZE        = (240, 240)
N_COLORS    = 16

os.makedirs(OUT_DIR, exist_ok=True)

IMAGES = {
    "kitten_wake":  f"{SPRITE_DIR}/kitten_wake_1776102423544.png",
    "kitten_sleep": f"{SPRITE_DIR}/kitten_sleep_1776102451224.png",
    "dolphin_wake": f"{SPRITE_DIR}/dolphin_wake_1776102474206.png",
    "dolphin_sleep":f"{SPRITE_DIR}/dolphin_sleep_1776102497897.png",
    "chicken_wake": f"{SPRITE_DIR}/chicken_wake_1776102520634.png",
    "chicken_sleep":f"{SPRITE_DIR}/chicken_sleep_1776102549228.png",
}


def rgb888_to_rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def convert(name, src_path):
    img = Image.open(src_path).convert("RGB")
    img = img.resize(SIZE, Image.LANCZOS)

    # Quantise to exactly N_COLORS
    img_p = img.quantize(colors=N_COLORS, method=Image.Quantize.MEDIANCUT)
    img_p = img_p.convert("RGB")          # back to RGB so we can read pixels

    # Re-quantise cleanly: collect all unique colours after quantise
    pixels = list(img_p.getdata())
    palette_set = []
    lookup = {}
    for px in pixels:
        if px not in lookup:
            if len(palette_set) < N_COLORS:
                lookup[px] = len(palette_set)
                palette_set.append(px)
            else:
                # find nearest
                best = min(range(len(palette_set)),
                           key=lambda i: sum((palette_set[i][c]-px[c])**2 for c in range(3)))
                lookup[px] = best

    # Pad palette to exactly 16 entries
    while len(palette_set) < N_COLORS:
        palette_set.append((0, 0, 0))

    # Build 4-bit packed pixel data
    data = bytearray()
    for i in range(0, len(pixels), 2):
        hi = lookup[pixels[i]]
        lo = lookup[pixels[i + 1]] if i + 1 < len(pixels) else 0
        data.append((hi << 4) | lo)

    # Write .bin file
    out_path = os.path.join(OUT_DIR, f"{name}.bin")
    with open(out_path, "wb") as f:
        f.write(data)

    # Compute RGB565 palette for themes.py
    pal565 = [rgb888_to_rgb565(*c) for c in palette_set]

    print(f"\n# {name}  ({len(data)} bytes → {out_path})")
    print(f'        "palette": [')
    for i in range(0, N_COLORS, 4):
        row = ", ".join(f"0x{v:04X}" for v in pal565[i:i+4])
        print(f"            {row},  # {i}-{i+3}")
    print(f'        ],')
    print(f'        "sprite_file": "sprites/{name}.bin",')

    return pal565


print("=" * 60)
print("Sprite conversion results")
print("=" * 60)

for name, path in IMAGES.items():
    if not os.path.exists(path):
        print(f"MISSING: {path}")
        continue
    convert(name, path)

print("\nDone. Upload the sprites/ directory to your ESP32.")
