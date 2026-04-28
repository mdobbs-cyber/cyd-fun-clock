#!/usr/bin/env python3
"""
convert_sprites.py  —  Convert PNG pixel art → 240x240 4-bit palette .bin files
Run this on the host PC any time you add new sprites.
Outputs go to sprites/ directory.
"""

from PIL import Image
import os

SRC = "/home/matt/.gemini/antigravity/brain/384bc580-247b-449f-9ff7-6888c641495e"
OUT = "/home/matt/Documents/aiapps/cyd-fun-clock/sprites"
SIZE = (240, 240)
N_COLORS = 16

os.makedirs(OUT, exist_ok=True)

IMAGES = {
    # Kitten
    "kitten_wake":    f"{SRC}/kitten_wake_1776102423544.png",
    "kitten_sleep":   f"{SRC}/kitten_sleep_1776102451224.png",
    "kitten_read":    f"{SRC}/kitten_read_1777387119950.png",
    # Dolphin
    "dolphin_wake":   f"{SRC}/dolphin_wake_1776102474206.png",
    "dolphin_sleep":  f"{SRC}/dolphin_sleep_1776102497897.png",
    "dolphin_read":   f"{SRC}/dolphin_read_1777387143593.png",
    # Chicken
    "chicken_wake":   f"{SRC}/chicken_wake_1776102520634.png",
    "chicken_sleep":  f"{SRC}/chicken_sleep_1776102549228.png",
    "chicken_read":   f"{SRC}/chicken_read_1777387644403.png",
    # Sloth
    "sloth_wake":     f"{SRC}/sloth_wake_1777387664041.png",
    "sloth_sleep":    f"{SRC}/sloth_sleep_1777387689363.png",
    "sloth_read":     f"{SRC}/sloth_read_1777387712091.png",
    # Puppy
    "puppy_wake":     f"{SRC}/puppy_wake_1777387735401.png",
    "puppy_sleep":    f"{SRC}/puppy_sleep_1777387759573.png",
    "puppy_read":     f"{SRC}/puppy_read_1777387778624.png",
    # Anteater
    "anteater_wake":  f"{SRC}/anteater_wake_1777387803369.png",
    "anteater_sleep": f"{SRC}/anteater_sleep_1777387828509.png",
    "anteater_read":  f"{SRC}/anteater_read_1777387851324.png",
}


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def convert(name, src):
    if not os.path.exists(src):
        print(f"  MISSING: {src}")
        return None

    img = Image.open(src).convert("RGB").resize(SIZE, Image.LANCZOS)
    img_q = img.quantize(colors=N_COLORS, method=Image.Quantize.MEDIANCUT).convert("RGB")

    pixels = list(img_q.getdata())
    pal_list, lookup = [], {}
    for px in pixels:
        if px not in lookup:
            if len(pal_list) < N_COLORS:
                lookup[px] = len(pal_list)
                pal_list.append(px)
            else:
                best = min(range(len(pal_list)),
                           key=lambda i: sum((pal_list[i][c]-px[c])**2 for c in range(3)))
                lookup[px] = best

    while len(pal_list) < N_COLORS:
        pal_list.append((0, 0, 0))

    data = bytearray()
    for i in range(0, len(pixels), 2):
        hi = lookup[pixels[i]]
        lo = lookup[pixels[i+1]] if i+1 < len(pixels) else 0
        data.append((hi << 4) | lo)

    out_path = os.path.join(OUT, f"{name}.bin")
    with open(out_path, "wb") as f:
        f.write(data)

    pal565 = [rgb565(*c) for c in pal_list]
    print(f"  {name}: {len(data)} bytes -> {out_path}")
    return pal565


print("=" * 60)
results = {}
for name, path in IMAGES.items():
    pal = convert(name, path)
    if pal:
        results[name] = pal

# Print palette block for themes.py
print("\n--- themes.py palette data ---")
for name, pal in results.items():
    print(f'  # {name}')
    rows = []
    for i in range(0, 16, 4):
        rows.append("            " + ", ".join(f"0x{v:04X}" for v in pal[i:i+4]) + ",")
    print("\n".join(rows))
    print()

print("Done. Upload sprites/ to your ESP32.")
