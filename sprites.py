# Optimized 4-bit palette sprite engine for MicroPython + ILI9341

def draw_palette_sprite(display, data, palette, x, y, scale=4):
    """
    Draws a 32x32 4-bit palette sprite.
    data: bytearray of 512 bytes (2 pixels per byte, high nibble first)
    palette: list of 16 RGB565 integers
    """
    w, h = 32, 32
    
    # Clip to screen
    if x < 0 or y < 0 or x + w*scale > display.width or y + h*scale > display.height:
        # For simplicity in this fun clock, we'll assume sprites stay on screen
        # but a robust system would clip here.
        pass

    display.set_window(x, y, x + w*scale - 1, y + h*scale - 1)
    
    # Each row in the buffer is w*scale pixels * 2 bytes (RGB565)
    row_buf = bytearray(w * scale * 2)
    
    display.dc.value(1)
    display.cs.value(0)
    
    for row_idx in range(h):
        # Unpack 4-bit data and fill row buffer
        for col_idx in range(w):
            byte_idx = (row_idx * w + col_idx) // 2
            val = data[byte_idx]
            
            # High nibble for even pixels, low nibble for odd pixels
            shift = 4 if (col_idx % 2 == 0) else 0
            color_idx = (val >> shift) & 0x0F
            
            color = palette[color_idx]
            # Big-endian for ILI9341
            c_hi = (color >> 8) & 0xFF
            c_lo = color & 0xFF
            
            # Repeat pixel horizontally by 'scale'
            for s in range(scale):
                pos = (col_idx * scale + s) * 2
                row_buf[pos] = c_hi
                row_buf[pos+1] = c_lo
        
        # Write the same scaled row buffer 'scale' times vertically
        for _ in range(scale):
            display.spi.write(row_buf)
            
    display.cs.value(1)
