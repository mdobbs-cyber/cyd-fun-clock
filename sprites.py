# Sprite engine for native 240×240 4-bit palette binary files.
# Binary format: raw packed 4-bit pixels, 28800 bytes for 240×240.
# High nibble = left pixel, low nibble = right pixel.

_cache = {}   # simple LRU-single sprite cache (avoids reloading same file)

def _load(path):
    """Load a .bin sprite file into a bytearray, with a one-entry cache."""
    if _cache.get("path") == path:
        return _cache["data"]
    with open(path, "rb") as f:
        data = f.read()
    _cache["path"] = path
    _cache["data"] = data
    return data


def draw_sprite_file(display, sprite_path, palette, x=0, y=0):
    """
    Draw a native 240×240 4-bit sprite directly from a binary file.
    palette: list of 16 RGB565 ints
    x, y  : top-left corner on screen (default 0,0 = full bleed)
    """
    data = _load(sprite_path)
    n = 240  # native size

    # Pre-build 32-byte palette lookup (big-endian RGB565 pairs)
    pal = bytearray(32)
    for i, c in enumerate(palette):
        pal[i * 2]     = (c >> 8) & 0xFF
        pal[i * 2 + 1] = c & 0xFF

    display.set_window(x, y, x + n - 1, y + n - 1)

    # Row buffer: 240 pixels × 2 bytes = 480 bytes
    row_buf = bytearray(n * 2)
    half_n  = n // 2   # bytes per row in the source data (120)

    display.dc.value(1)
    display.cs.value(0)

    for row in range(n):
        row_off = row * half_n
        for col in range(n):
            val = data[row_off + col // 2]
            idx = (val >> 4) if (col & 1) == 0 else (val & 0x0F)
            p = idx * 2
            pos = col * 2
            row_buf[pos]     = pal[p]
            row_buf[pos + 1] = pal[p + 1]
        display.spi.write(row_buf)

    display.cs.value(1)


def draw_palette_sprite(display, data, palette, x, y, scale=4):
    """
    Legacy helper: draws an NxN 4-bit palette sprite from an in-memory bytearray.
    Kept for backward compatibility with any callers that haven't moved to files yet.
    """
    n = int((len(data) * 2) ** 0.5)
    display.set_window(x, y, x + n * scale - 1, y + n * scale - 1)
    row_buf = bytearray(n * scale * 2)
    display.dc.value(1)
    display.cs.value(0)
    for row_idx in range(n):
        for col_idx in range(n):
            byte_idx  = (row_idx * n + col_idx) // 2
            val       = data[byte_idx]
            shift     = 4 if (col_idx & 1) == 0 else 0
            color     = palette[(val >> shift) & 0x0F]
            c_hi      = (color >> 8) & 0xFF
            c_lo      = color & 0xFF
            for s in range(scale):
                pos = (col_idx * scale + s) * 2
                row_buf[pos]     = c_hi
                row_buf[pos + 1] = c_lo
        for _ in range(scale):
            display.spi.write(row_buf)
    display.cs.value(1)
