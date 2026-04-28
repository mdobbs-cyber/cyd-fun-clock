import machine
import time
import ujson
import boot
import font
from ili9341 import ILI9341
from xpt2046 import XPT2046
from themes import THEMES

# ── Sprite renderer (self-contained, no external module dependency) ────────────
_spr_cache = {}

def _blit_sprite(display, path, palette, x=0, y=0):
    """Load a 240x240 4-bit .bin sprite and blit it to the display."""
    if _spr_cache.get('p') == path:
        data = _spr_cache['d']
    else:
        with open(path, 'rb') as f:
            data = f.read()
        _spr_cache['p'] = path
        _spr_cache['d'] = data

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
    for row in range(n):
        off = row * half_n
        for col in range(n):
            v   = data[off + col // 2]
            idx = (v >> 4) if (col & 1) == 0 else (v & 0x0F)
            p   = idx * 2
            pos = col * 2
            row_buf[pos]     = pal[p]
            row_buf[pos + 1] = pal[p + 1]
        display.spi.write(row_buf)
    display.cs.value(1)

# ── CYD Pinout ─────────────────────────────────────────────────────────────────
SPI_SCK, SPI_MOSI, SPI_MISO = 14, 13, 12
DISP_CS, DISP_DC, DISP_BL   = 15, 2, 21
TOUCH_CLK, TOUCH_CS, TOUCH_DIN, TOUCH_DO = 25, 33, 32, 39
LDR_PIN = 34
RGB_R, RGB_G, RGB_B = 4, 16, 17

# ── Layout constants ───────────────────────────────────────────────────────────
# Sprite is 240x240 native, centred horizontally on the 320x240 screen.
SPRITE_X = (320 - 240) // 2   # 40
SPRITE_Y = 0

BANNER_Y   = 4
BANNER_H   = 22
TIME_Y     = 212
TIME_H     = 28
TIME_SCALE = 3
TIME_X     = (320 - 5 * 7 * TIME_SCALE) // 2   # ~107


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

    # ── 3. State ────────────────────────────────────────────────────────────────
    theme_keys    = sorted(THEMES.keys())
    theme_idx     = theme_keys.index(config['active_theme']) \
                    if config['active_theme'] in theme_keys else 0
    last_tick     = 0
    current_state = None   # "WAKE" | "READ" | "SLEEP"
    last_time_str = ""

    # ── Helpers ─────────────────────────────────────────────────────────────────
    def parse_hhmm(s):
        """Return minutes since midnight for 'HH:MM', or -1 if blank/invalid."""
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
        """Return 'WAKE', 'READ', or 'SLEEP' for the given local-time tuple."""
        is_weekend  = t[6] >= 5
        now_m = t[3] * 60 + t[4]

        wake_m  = parse_hhmm(cfg['wake_weekend']  if is_weekend else cfg['wake_weekday'])
        sleep_m = parse_hhmm(cfg['sleep_weekend'] if is_weekend else cfg['sleep_weekday'])

        if is_weekend:
            read_start_m = parse_hhmm(cfg.get('read_start_weekend', ''))
            read_end_m   = parse_hhmm(cfg.get('read_end_weekend',   ''))
        else:
            read_start_m = parse_hhmm(cfg.get('read_start_weekday', ''))
            read_end_m   = parse_hhmm(cfg.get('read_end_weekday',   ''))

        # Reading window takes priority (must be within wake hours)
        if read_start_m >= 0 and read_end_m >= 0:
            if read_start_m <= now_m < read_end_m:
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
        bg      = theme[f'bg_{state.lower()}']
        fg      = theme[f'fg_{state.lower()}']
        palette = theme[f'palette_{state.lower()}']
        sprite  = theme[f'sprite_{state.lower()}']
        return bg, fg, palette, sprite

    def full_redraw(state, theme, time_str):
        bg, fg, palette, sprite = theme_vals(theme, state)
        display.clear(bg)
        _blit_sprite(display, sprite, palette, SPRITE_X, SPRITE_Y)
        draw_banner(state, bg)
        draw_time(time_str, fg, bg)

    # ── Demo Loop ────────────────────────────────────────────────────────────────
    def demo_loop():
        """Cycle all animal × state combinations every 5 s. Touch skips ahead."""
        DEMO_SECS = 5
        # Build sequence: for each animal show wake → read → sleep
        sequence = []
        for k in theme_keys:
            sequence.append((k, "WAKE"))
            sequence.append((k, "READ"))
            sequence.append((k, "SLEEP"))

        idx = 0
        while True:
            animal_key, state = sequence[idx]
            theme    = THEMES[animal_key]
            t        = get_local_time()
            time_str = "{:02d}:{:02d}".format(t[3], t[4])
            bg, fg, palette, sprite = theme_vals(theme, state)

            full_redraw(state, theme, time_str)

            if state == "WAKE":
                set_led(0, 512, 0)
            elif state == "READ":
                set_led(0, 0, 512)    # Soft blue for reading
            else:
                set_led(256, 128, 0)

            deadline = time.time() + DEMO_SECS
            while time.time() < deadline:
                if touch.get_touch():
                    time.sleep(0.3)
                    break
                t2  = get_local_time()
                ts2 = "{:02d}:{:02d}".format(t2[3], t2[4])
                if ts2 != time_str:
                    draw_time(ts2, fg, bg)
                    time_str = ts2
                if config['brightness_auto']:
                    raw = ldr.read()
                    led_bl.duty(max(100, min(1023, (4095 - raw) // 4)))
                time.sleep(0.1)

            idx = (idx + 1) % len(sequence)

    # ── Main Loop ────────────────────────────────────────────────────────────────
    if config.get('demo', False):
        print("[demo] Starting demo — cycling all states every 5 s")
        demo_loop()   # never returns

    while True:
        now = time.time()

        # Touch → cycle theme
        if touch.get_touch():
            theme_idx = (theme_idx + 1) % len(theme_keys)
            config['active_theme'] = theme_keys[theme_idx]
            current_state = None
            last_time_str = ""
            time.sleep(0.3)

        # Periodic update (every 60 s, or forced on first run / theme change)
        if now - last_tick >= 60 or current_state is None:
            t        = get_local_time()
            state    = get_state(t, config)
            theme    = THEMES[config['active_theme']]
            bg, fg, palette, sprite = theme_vals(theme, state)
            time_str = "{:02d}:{:02d}".format(t[3], t[4])

            if state != current_state:
                current_state = state
                full_redraw(state, theme, time_str)

                if state == "WAKE":
                    set_led(0, 512, 0)
                elif state == "READ":
                    set_led(0, 0, 512)    # Soft blue for reading time
                else:
                    set_led(256, 128, 0)  # Soft amber nightlight

            elif time_str != last_time_str:
                draw_time(time_str, fg, bg)

            last_time_str = time_str
            last_tick = now

        if config['brightness_auto']:
            raw = ldr.read()
            led_bl.duty(max(100, min(1023, (4095 - raw) // 4)))

        time.sleep(0.1)


if __name__ == "__main__":
    main()
