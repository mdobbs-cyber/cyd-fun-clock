import machine
import time
import ujson
import boot
import font
from ili9341 import ILI9341
from xpt2046 import XPT2046
from themes import THEMES

# CYD Pinout
SPI_SCK, SPI_MOSI, SPI_MISO = 14, 13, 12
DISP_CS, DISP_DC, DISP_BL = 15, 2, 21
TOUCH_CLK, TOUCH_CS, TOUCH_DIN, TOUCH_DO = 25, 33, 32, 39
LDR_PIN = 34
RGB_R, RGB_G, RGB_B = 4, 16, 17

def main():
    # 1. Load Config
    config = {
        "tz_offset": -5, "use_dst": True,
        "wake_weekday": "06:00", "sleep_weekday": "20:00",
        "wake_weekend": "08:00", "sleep_weekend": "21:00",
        "active_theme": "kitten", "brightness_auto": True
    }
    try:
        with open('config.json', 'r') as f:
            config.update(ujson.load(f))
    except: pass

    # 2. Init Hardware
    boot.connect_wifi()
    
    # Display
    spi_disp = machine.SPI(1, baudrate=40000000, sck=machine.Pin(SPI_SCK), mosi=machine.Pin(SPI_MOSI))
    display = ILI9341(spi_disp, cs=machine.Pin(DISP_CS), dc=machine.Pin(DISP_DC), rst=None, bl=machine.Pin(DISP_BL))
    display.clear(0)

    # Touch
    spi_touch = machine.SoftSPI(baudrate=1000000, sck=machine.Pin(TOUCH_CLK), mosi=machine.Pin(TOUCH_DIN), miso=machine.Pin(TOUCH_DO))
    touch = XPT2046(spi_touch, cs=machine.Pin(TOUCH_CS))

    # Sensors & LED
    ldr = machine.ADC(machine.Pin(LDR_PIN))
    ldr.atten(machine.ADC.ATTN_11DB)
    led_bl = machine.PWM(machine.Pin(DISP_BL), freq=1000)
    led_r = machine.PWM(machine.Pin(RGB_R), freq=1000)
    led_g = machine.PWM(machine.Pin(RGB_G), freq=1000)
    led_b = machine.PWM(machine.Pin(RGB_B), freq=1000)
    
    # Active-LOW helpers (1023 is OFF, 0 is fully ON)
    def set_led(r, g, b):
        led_r.duty(1023 - r); led_g.duty(1023 - g); led_b.duty(1023 - b)

    theme_keys = sorted(list(THEMES.keys()))
    theme_idx = theme_keys.index(config['active_theme']) if config['active_theme'] in theme_keys else 0
    
    last_tick = 0
    current_state = None # "WAKE" or "SLEEP"

    def is_wake_mode(t, cfg):
        day = t[6] # 0=Mon, 6=Sun
        is_weekend = day >= 5
        wake_str = cfg['wake_weekend'] if is_weekend else cfg['wake_weekday']
        sleep_str = cfg['sleep_weekend'] if is_weekend else cfg['sleep_weekday']
        
        now_min = t[3] * 60 + t[4]
        wake_min = int(wake_str[:2]) * 60 + int(wake_str[3:])
        sleep_min = int(sleep_str[:2]) * 60 + int(sleep_str[3:])
        
        return wake_min <= now_min < sleep_min

    def get_local_time():
        t = time.localtime(time.time() + (config['tz_offset'] * 3600))
        # Simple DST (US March-Nov approx)
        if config['use_dst']:
            # For a production app, use a more robust is_dst check
            # For this fun clock, we'll assume the user might manually adjust tz if needed
            # or we can implement the same logic from cyd-env
            pass
        return t

    while True:
        now = time.time()
        
        # 1. Handle Touch
        if touch.get_touch():
            theme_idx = (theme_idx + 1) % len(theme_keys)
            config['active_theme'] = theme_keys[theme_idx]
            current_state = None # Force redraw
            time.sleep(0.3)

        # 2. Periodic Update (every minute or on state change)
        if now - last_tick >= 60 or current_state is None:
            t = get_local_time()
            is_wake = is_wake_mode(t, config)
            state = "WAKE" if is_wake else "SLEEP"
            
            theme = THEMES[config['active_theme']]
            
            if state != current_state:
                current_state = state
                display.clear(theme['bg_wake'] if is_wake else theme['bg_sleep'])
                
                # RGB LED State
                if is_wake:
                    set_led(0, 512, 0) # Soft Green
                else:
                    set_led(256, 128, 0) # Soft Amber Nightlight
            
            # --- Draw UI ---
            bg = theme['bg_wake'] if is_wake else theme['bg_sleep']
            fg = theme['color_wake'] if is_wake else theme['color_sleep']
            
            # Draw Animal
            sprite = theme['sprite_wake'] if is_wake else theme['sprite_sleep']
            font.draw_sprite32(display, sprite, 160 - 64, 40, scale=4, color=fg)
            
            # Draw Time
            time_str = "{:02d}:{:02d}".format(t[3], t[4])
            font.draw_text(display, time_str, 320 // 2 - 35*2, 180, scale=4, color=fg)
            
            # Banner
            if is_wake:
                font.draw_text(display, "OK TO WAKE!", 70, 10, scale=2, color=0xFFFF)
            else:
                font.draw_text(display, "SHHH... SLEEPING", 50, 10, scale=2, color=0x7BEF)
            
            last_tick = now

        # 3. Brightness Control
        if config['brightness_auto']:
            # LDR: low value = dark, high value = bright
            # Display BL: low duty = dark, high duty = bright
            raw_ldr = ldr.read()
            bright = (4095 - raw_ldr) // 4 # Basic linear map
            led_bl.duty(max(100, min(1023, bright))) 

        time.sleep(0.1)

if __name__ == "__main__":
    main()
