import machine
import time
import ujson
import boot
import font
import sprites
from ili9341 import ILI9341
from xpt2046 import XPT2046
from themes import THEMES

# CYD Pinout
SPI_SCK, SPI_MOSI, SPI_MISO = 14, 13, 12
DISP_CS, DISP_DC, DISP_BL = 15, 2, 21
TOUCH_CLK, TOUCH_CS, TOUCH_DIN, TOUCH_DO = 25, 33, 32, 39
LDR_PIN = 34
RGB_R, RGB_G, RGB_B = 4, 16, 17

# ── Layout constants ──────────────────────────────────────────────────────────
# Screen: 320 x 240 landscape
# Sprite: 24px * scale=10  →  240 x 240, centered at x=40
SPRITE_SCALE = 10
SPRITE_SIZE  = 24 * SPRITE_SCALE          # 240
SPRITE_X     = (320 - SPRITE_SIZE) // 2   # 40  (40 px background strips each side)
SPRITE_Y     = 0

# Top banner strip  (overlaid on sprite, solid bg band)
BANNER_Y   = 4
BANNER_H   = 22

# Bottom time strip (overlaid on sprite, solid bg band)
TIME_Y     = 212
TIME_H     = 28
TIME_SCALE = 3
# "HH:MM" at scale 3 = 5 chars × 7px/char × 3 = 105 px wide
TIME_X     = (320 - 5 * 7 * TIME_SCALE) // 2   # ~107


def main():
    # ── 1. Load Config ─────────────────────────────────────────────────────────
    config = {
        "tz_offset": -5, "use_dst": True,
        "wake_weekday": "06:00", "sleep_weekday": "20:00",
        "wake_weekend": "08:00", "sleep_weekend": "21:00",
        "active_theme": "kitten", "brightness_auto": True
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
        # Active-LOW: 1023 = OFF, 0 = full ON
        led_r.duty(1023 - r)
        led_g.duty(1023 - g)
        led_b.duty(1023 - b)

    # ── 3. State ────────────────────────────────────────────────────────────────
    theme_keys  = sorted(THEMES.keys())
    theme_idx   = theme_keys.index(config['active_theme']) \
                  if config['active_theme'] in theme_keys else 0
    last_tick   = 0
    current_state   = None   # "WAKE" | "SLEEP"
    last_time_str   = ""

    # ── Helpers ─────────────────────────────────────────────────────────────────
    def is_dst(year, month, day, hour):
        """Approximate US DST: 2nd Sunday of March → 1st Sunday of November."""
        if month < 3 or month > 11: return False
        if 3 < month < 11:          return True
        first = time.mktime((year, month, 1, 0, 0, 0, 0, 0))
        wday  = time.localtime(first)[6]          # 0=Mon … 6=Sun
        if month == 3:
            second_sun = 1 + (6 - wday) % 7 + 7  # 2nd Sunday
            return day > second_sun or (day == second_sun and hour >= 2)
        # November
        first_sun = 1 + (6 - wday) % 7
        return day < first_sun or (day == first_sun and hour < 2)

    def get_local_time():
        offset = config['tz_offset']
        t = time.localtime(time.time() + offset * 3600)
        if config.get('use_dst', False) and is_dst(t[0], t[1], t[2], t[3]):
            t = time.localtime(time.time() + (offset + 1) * 3600)
        return t

    def is_wake_mode(t, cfg):
        day = t[6]
        is_weekend  = day >= 5
        wake_str  = cfg['wake_weekend']  if is_weekend else cfg['wake_weekday']
        sleep_str = cfg['sleep_weekend'] if is_weekend else cfg['sleep_weekday']
        now_m   = t[3] * 60 + t[4]
        wake_m  = int(wake_str[:2])  * 60 + int(wake_str[3:])
        sleep_m = int(sleep_str[:2]) * 60 + int(sleep_str[3:])
        return wake_m <= now_m < sleep_m

    # ── Drawing helpers ──────────────────────────────────────────────────────────
    def draw_banner(is_wake, fg, bg):
        """Draw the top banner strip — erase first so old text is gone."""
        display.fill_rect(0, BANNER_Y - 2, 320, BANNER_H + 4, bg)
        if is_wake:
            msg   = "OK TO WAKE!"
            color = 0xFFFF
        else:
            msg   = "SHHH... SLEEPING"
            color = 0x7BEF
        x = (320 - len(msg) * 7 * 2) // 2
        font.draw_text(display, msg, max(0, x), BANNER_Y, scale=2, color=color)

    def draw_time(time_str, fg, bg):
        """Erase the previous time, then draw the new one at the same position."""
        display.fill_rect(0, TIME_Y - 2, 320, TIME_H + 4, bg)
        font.draw_text(display, time_str, TIME_X, TIME_Y, scale=TIME_SCALE, color=fg)

    def full_redraw(is_wake, theme, time_str):
        """Full screen redraw: background → sprite → text overlays."""
        bg     = theme['bg_wake']  if is_wake else theme['bg_sleep']
        fg     = theme['fg_wake']  if is_wake else theme['fg_sleep']
        sprite = theme['sprite_wake'] if is_wake else theme['sprite_sleep']

        # 1. Clear entire screen with theme background
        display.clear(bg)

        # 2. Blit full-screen sprite (240×240, centred horizontally)
        sprites.draw_palette_sprite(
            display, sprite, theme['palette'],
            SPRITE_X, SPRITE_Y, scale=SPRITE_SCALE
        )

        # 3. Overlay text panels (erases local strip, draws text)
        draw_banner(is_wake, fg, bg)
        draw_time(time_str, fg, bg)

    # ── Main Loop ────────────────────────────────────────────────────────────────
    while True:
        now = time.time()

        # Touch → cycle theme → force full redraw
        if touch.get_touch():
            theme_idx = (theme_idx + 1) % len(theme_keys)
            config['active_theme'] = theme_keys[theme_idx]
            current_state = None
            last_time_str = ""
            time.sleep(0.3)

        # Periodic update (every 60 s)
        if now - last_tick >= 60 or current_state is None:
            t        = get_local_time()
            is_wake  = is_wake_mode(t, config)
            state    = "WAKE" if is_wake else "SLEEP"
            theme    = THEMES[config['active_theme']]
            bg       = theme['bg_wake']  if is_wake else theme['bg_sleep']
            fg       = theme['fg_wake']  if is_wake else theme['fg_sleep']
            time_str = "{:02d}:{:02d}".format(t[3], t[4])

            if state != current_state:
                # ── State transition: full redraw (sprite changes too) ──────────
                current_state = state
                full_redraw(is_wake, theme, time_str)

                if is_wake:
                    set_led(0, 512, 0)    # Soft green
                else:
                    set_led(256, 128, 0)  # Soft amber nightlight

            elif time_str != last_time_str:
                # ── Same state, only time digits changed: erase + redraw time ──
                draw_time(time_str, fg, bg)

            last_time_str = time_str
            last_tick = now

        # Auto-brightness via LDR
        if config['brightness_auto']:
            raw = ldr.read()
            bright = (4095 - raw) // 4       # invert: dark room → low brightness
            led_bl.duty(max(100, min(1023, bright)))

        time.sleep(0.1)


if __name__ == "__main__":
    main()
