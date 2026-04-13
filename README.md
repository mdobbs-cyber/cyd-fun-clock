# CYD Animal Companion Clock 🐱🐬🐥

A fun, kid-friendly "OK to Wake" clock for the **Cheap Yellow Display (ESP32-2432S028)**.

This project helps children know when it's time to sleep and when it's okay to wake up through visual cues, animations, and color-coded lighting.

## ✨ Features

- **Three Animal Themes**: Luna the Kitten, Splash the Dolphin, and Peep the Chicken.
- **"OK to Wake" Logic**:
  - Displays a bright "OK TO WAKE!" banner at wake time.
  - Shows a sleepy mascot and dark colors during rest time.
- **Smart Scheduling**: Separate wake/sleep times for weekdays and weekends.
- **Hardware Integration**:
  - **RGB LED**: Glows Green for wake time and Soft Amber for nightlight mode.
  - **Auto-Brightness**: Uses the LDR sensor to dim the screen automatically at night.
  - **Touch Cycling**: Tap the screen to switch between animal friends.
- **Internet Sync**: Automatically sets the time over WiFi via NTP.

## 🛠️ Hardware Requirements

- **Cheap Yellow Display (CYD)** - ESP32-2432S028
- MicroPython firmware installed.
- (Optional) microSD card for future theme expansion.

## 🚀 Installation

1. **Clone the repo**:
   ```bash
   git clone https://github.com/yourusername/cyd-fun-clock.git
   ```
2. **Configure**:
   - Copy `config.json.example` to `config.json`.
   - Update `wifi_ssid`, `wifi_pass`, and your preferred schedule.
3. **Upload**:
   - Upload all `.py` and `.json` files to your ESP32.
4. **Boot**:
   - Run `main.py`!

## 📂 File Structure

- `main.py`: Core logic and hardware control.
- `themes.py`: Pixel art and color definitions.
- `font.py`: Display helper for text and sprites.
- `boot.py`: WiFi and Time initialization.
- `config.json`: Private settings (ignored by git).
