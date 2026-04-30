import machine
import time
import ujson
import boot
import font
from ili9341 import ILI9341
from xpt2046 import XPT2046
from themes import THEMES

# ── Sprite renderer (self-contained, no external module dependency) ────────────

def _blit_sprite(display, path, palette, x=0, y=0):
    """Load a 240x240 4-bit .bin sprite and blit it to the display in memory-efficient chunks."""
    n = 240
    pal = bytearray(32)
    for i, c in enumerate(palette):
        pal[i * 2]     = (c >> 8) & 0xFF
        pal[i * 2 + 1] = c & 0xFF

    display.set_window(x, y, x + n - 1, y + n - 1)
    row_buf = bytearray(n * 2)
    half_n  = n // 2

    display.dc.value(1)
    display.cs.value(0)
    try:
        with open(path, 'rb') as f:
            # Read in chunks of 10 rows (1200 bytes vs 28.8KB) to avoid MemoryError
            chunk_rows = 10
            for r_block in range(0, n, chunk_rows):
                chunk = f.read(half_n * chunk_rows)
                if not chunk:
                    break
                for r in range(min(chunk_rows, n - r_block)):
                    off = r * half_n
                    for col in range(n):
                        if off + col // 2 >= len(chunk):
                            break
                        v   = chunk[off + col // 2]
                        idx = (v >> 4) if (col & 1) == 0 else (v & 0x0F)
                        p   = idx * 2
                        pos = col * 2
                        row_buf[pos]     = pal[p]
                        row_buf[pos + 1] = pal[p + 1]
                    display.spi.write(row_buf)
    except Exception as e:
        print("Sprite error:", path, e)
    display.cs.value(1)

# ── CYD Pinout ─────────────────────────────────────────────────────────────────
SPI_SCK, SPI_MOSI, SPI_MISO = 14, 13, 12
DISP_CS, DISP_DC, DISP_BL   = 15, 2, 21
TOUCH_CLK, TOUCH_CS, TOUCH_DIN, TOUCH_DO = 25, 33, 32, 39
LDR_PIN = 34
RGB_R, RGB_G, RGB_B = 4, 16, 17

# ── Layout constants ───────────────────────────────────────────────────────────
SPRITE_X = (320 - 240) // 2   # 40 — centred horizontally
SPRITE_Y = 0

BANNER_Y   = 4
BANNER_H   = 22
TIME_Y     = 212
TIME_H     = 28
TIME_SCALE = 3
# "12:00PM" = 7 chars x 7px x scale3 = 147px wide
TIME_X     = (320 - 7 * 7 * TIME_SCALE) // 2   # ~86

DEMO_SECS      = 5      # seconds per demo slide
HOLD_MS        = 2000   # ms to hold for a long-press


def fmt_time(h, m):
    """Return a 7-char 12-hour AM/PM string, e.g. '12:00PM' or ' 9:30AM'."""
    suffix = "AM" if h < 12 else "PM"
    h12    = h % 12 or 12
    return "{:2d}:{:02d}{}".format(h12, m, suffix)


def main():
    # ── 1. Load Config ─────────────────────────────────────────────────────────
    config = {
        "tz_offset": -5, "use_dst": True,
        "wake_weekday":       "06:00", "sleep_weekday":      "20:00",
        "wake_weekend":       "08:00", "sleep_weekend":      "21:00",
        "read_start_weekday": "",      "read_end_weekday":   "",
        "read_start_weekend": "",      "read_end_weekend":   "",
        "active_theme": "kitten", "brightness_auto": True,
        "demo": False,
    }
    try:
        with open('config.json', 'r') as f:
            config.update(ujson.load(f))
    except:
        pass

    # ── 2. Init Hardware ────────────────────────────────────────────────────────
    boot.connect_wifi()

    spi_disp = machine.SPI(1, baudrate=40000000,
                           sck=machine.Pin(SPI_SCK), mosi=machine.Pin(SPI_MOSI))
    display = ILI9341(spi_disp, cs=machine.Pin(DISP_CS),
                      dc=machine.Pin(DISP_DC), rst=None, bl=machine.Pin(DISP_BL))
    display.clear(0)

    spi_touch = machine.SoftSPI(baudrate=1000000,
                                sck=machine.Pin(TOUCH_CLK),
                                mosi=machine.Pin(TOUCH_DIN),
                                miso=machine.Pin(TOUCH_DO))
    touch = XPT2046(spi_touch, cs=machine.Pin(TOUCH_CS))

    ldr    = machine.ADC(machine.Pin(LDR_PIN))
    ldr.atten(machine.ADC.ATTN_11DB)
    led_bl = machine.PWM(machine.Pin(DISP_BL), freq=1000)
    led_r  = machine.PWM(machine.Pin(RGB_R),   freq=1000)
    led_g  = machine.PWM(machine.Pin(RGB_G),   freq=1000)
    led_b  = machine.PWM(machine.Pin(RGB_B),   freq=1000)

    def set_led(r, g, b):
        led_r.duty(1023 - r)
        led_g.duty(1023 - g)
        led_b.duty(1023 - b)

    # ── 3. Runtime state ────────────────────────────────────────────────────────
    theme_keys    = sorted(THEMES.keys())
    theme_idx     = theme_keys.index(config['active_theme']) \
                    if config['active_theme'] in theme_keys else 0

    # Demo sequence: every animal in wake → read → sleep order
    demo_seq = [(k, s) for k in theme_keys for s in ("WAKE", "READ", "SLEEP")]

    demo_active   = config.get('demo', False)
    demo_idx      = 0
    demo_deadline = 0   # time.time() by which current slide auto-advances

    last_tick     = 0
    current_state = None
    last_time_str = ""

    # ── Helpers ─────────────────────────────────────────────────────────────────
    def parse_hhmm(s):
        try:
            return int(s[:2]) * 60 + int(s[3:])
        except:
            return -1

    def is_dst(year, month, day, hour):
        if month < 3 or month > 11: return False
        if 3 < month < 11:          return True
        first = time.mktime((year, month, 1, 0, 0, 0, 0, 0))
        wday  = time.localtime(first)[6]
        if month == 3:
            second_sun = 1 + (6 - wday) % 7 + 7
            return day > second_sun or (day == second_sun and hour >= 2)
        first_sun = 1 + (6 - wday) % 7
        return day < first_sun or (day == first_sun and hour < 2)

    def get_local_time():
        offset = config['tz_offset']
        t = time.localtime(time.time() + offset * 3600)
        if config.get('use_dst', False) and is_dst(t[0], t[1], t[2], t[3]):
            t = time.localtime(time.time() + (offset + 1) * 3600)
        return t

    def get_state(t, cfg):
        is_weekend   = t[6] >= 5
        now_m        = t[3] * 60 + t[4]
        wake_m       = parse_hhmm(cfg['wake_weekend']  if is_weekend else cfg['wake_weekday'])
        sleep_m      = parse_hhmm(cfg['sleep_weekend'] if is_weekend else cfg['sleep_weekday'])
        read_start_m = parse_hhmm(cfg.get('read_start_weekend' if is_weekend else 'read_start_weekday', ''))
        read_end_m   = parse_hhmm(cfg.get('read_end_weekend'   if is_weekend else 'read_end_weekday',   ''))

        if read_start_m >= 0 and read_end_m >= 0 and read_start_m <= now_m < read_end_m:
            return "READ"
        if wake_m >= 0 and sleep_m >= 0 and wake_m <= now_m < sleep_m:
            return "WAKE"
        return "SLEEP"

    # ── Drawing helpers ──────────────────────────────────────────────────────────
    BANNERS = {
        "WAKE":  ("OK TO WAKE!",      0xFFFF),
        "READ":  ("READING TIME!",    0xFFE0),
        "SLEEP": ("SHHH... SLEEPING", 0x7BEF),
    }

    def draw_banner(state, bg):
        msg, color = BANNERS[state]
        display.fill_rect(0, BANNER_Y - 2, 320, BANNER_H + 4, bg)
        x = (320 - len(msg) * 7 * 2) // 2
        font.draw_text(display, msg, max(0, x), BANNER_Y, scale=2, color=color)

    def draw_time(time_str, fg, bg):
        display.fill_rect(0, TIME_Y - 2, 320, TIME_H + 4, bg)
        font.draw_text(display, time_str, TIME_X, TIME_Y, scale=TIME_SCALE, color=fg)

    def theme_vals(theme, state):
        s = state.lower()
        return theme['bg_'+s], theme['fg_'+s], theme['palette_'+s], theme['sprite_'+s]

    def full_redraw(state, theme, time_str):
        bg, fg, palette, sprite = theme_vals(theme, state)
        display.clear(bg)
        _blit_sprite(display, sprite, palette, SPRITE_X, SPRITE_Y)
        draw_banner(state, bg)
        draw_time(time_str, fg, bg)

    def apply_led(state):
        if state == "WAKE":
            set_led(0, 512, 0)
        elif state == "READ":
            set_led(0, 0, 512)
        else:
            set_led(256, 128, 0)

    def show_toast(msg, color=0xFFFF):
        """Flash a short centre message on a black bar for ~1 second."""
        display.fill_rect(0, 100, 320, 40, 0x0000)
        x = (320 - len(msg) * 7 * 2) // 2
        font.draw_text(display, msg, max(0, x), 110, scale=2, color=color)
        time.sleep(1)

    def check_touch():
        """
        Returns:
          'tap'  — brief touch (< HOLD_MS)
          'hold' — long press (>= HOLD_MS) — use to toggle demo mode
          None   — no touch detected
        """
        if not touch.get_touch():
            return None
        start = time.ticks_ms()
        while touch.get_touch():
            if time.ticks_diff(time.ticks_ms(), start) >= HOLD_MS:
                # Wait for finger to lift before returning
                while touch.get_touch():
                    time.sleep(0.05)
                return 'hold'
            time.sleep(0.05)
        return 'tap'

    # ── Main Loop ────────────────────────────────────────────────────────────────
    while True:
        now     = time.time()
        gesture = check_touch()

        # ── Long-press: toggle demo mode ───────────────────────────────────────
        if gesture == 'hold':
            demo_active = not demo_active
            demo_idx      = 0
            demo_deadline = 0   # trigger immediate slide draw
            current_state = None
            last_time_str = ""
            if demo_active:
                show_toast("DEMO  ON", 0xFFE0)
            else:
                show_toast("DEMO  OFF", 0xF800)

        # ══════════════════════════════════════════════════════════════════════
        # DEMO MODE
        # ══════════════════════════════════════════════════════════════════════
        elif demo_active:
            if gesture == 'tap':
                # Skip to next slide immediately
                demo_idx      = (demo_idx + 1) % len(demo_seq)
                demo_deadline = 0

            if now >= demo_deadline:
                animal_key, state = demo_seq[demo_idx]
                theme    = THEMES[animal_key]
                t        = get_local_time()
                time_str = fmt_time(t[3], t[4])

                full_redraw(state, theme, time_str)
                apply_led(state)

                last_time_str = time_str
                demo_deadline = now + DEMO_SECS
                demo_idx      = (demo_idx + 1) % len(demo_seq)

            else:
                # Between slides — keep time current
                t        = get_local_time()
                time_str = fmt_time(t[3], t[4])
                if time_str != last_time_str:
                    # Recover current slide info for the bg/fg colours
                    prev_idx   = (demo_idx - 1) % len(demo_seq)
                    ak, st     = demo_seq[prev_idx]
                    bg, fg, _, _ = theme_vals(THEMES[ak], st)
                    draw_time(time_str, fg, bg)
                    last_time_str = time_str

        # ══════════════════════════════════════════════════════════════════════
        # NORMAL MODE
        # ══════════════════════════════════════════════════════════════════════
        else:
            if gesture == 'tap':
                theme_idx = (theme_idx + 1) % len(theme_keys)
                config['active_theme'] = theme_keys[theme_idx]
                current_state = None
                last_time_str = ""

            if now - last_tick >= 60 or current_state is None:
                t        = get_local_time()
                state    = get_state(t, config)
                theme    = THEMES[config['active_theme']]
                bg, fg, palette, sprite = theme_vals(theme, state)
                time_str = fmt_time(t[3], t[4])

                if state != current_state:
                    current_state = state
                    full_redraw(state, theme, time_str)
                    apply_led(state)

                elif time_str != last_time_str:
                    draw_time(time_str, fg, bg)

                last_time_str = time_str
                last_tick     = now

        # ── Auto-brightness ────────────────────────────────────────────────────
        if config['brightness_auto']:
            raw = ldr.read()
            led_bl.duty(max(100, min(1023, (4095 - raw) // 4)))

        time.sleep(0.05)   # tighter loop needed for hold detection


if __name__ == "__main__":
    main()
