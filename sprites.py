def draw_palette_sprite(display, data, palette, x, y, scale=4):
    """
    Draws an NxN 4-bit palette sprite.
    data: bytearray of N*N/2 bytes (2 pixels per byte, high nibble first)
    palette: list of 16 RGB565 integers
    Size is derived from data length: 288 bytes = 24x24, 512 bytes = 32x32
    """
    n = int((len(data) * 2) ** 0.5)  # e.g. 288*2=576, sqrt=24
    
    display.set_window(x, y, x + n*scale - 1, y + n*scale - 1)
    
    # One row buffer: n pixels wide, scaled horizontally
    row_buf = bytearray(n * scale * 2)
    
    display.dc.value(1)
    display.cs.value(0)
    
    for row_idx in range(n):
        for col_idx in range(n):
            byte_idx = (row_idx * n + col_idx) // 2
            val = data[byte_idx]
            shift = 4 if (col_idx % 2 == 0) else 0
            color_idx = (val >> shift) & 0x0F
            color = palette[color_idx]
            c_hi = (color >> 8) & 0xFF
            c_lo = color & 0xFF
            for s in range(scale):
                pos = (col_idx * scale + s) * 2
                row_buf[pos] = c_hi
                row_buf[pos + 1] = c_lo
        for _ in range(scale):
            display.spi.write(row_buf)
    
    display.cs.value(1)
