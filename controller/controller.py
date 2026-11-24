import time
import redis
import requests
from gpiozero import Button
from rpi_ws281x import PixelStrip, Color

# Kano Light Circle HAT Pinout
LED_COUNT = 10
LED_PIN = 18          # GPIO 22 (WS2812 Data)
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 10   # 0-255
LED_INVERT = False
LED_CHANNEL = 0

BUTTON_PIN = 3        # GPIO 3 (Pulled down; HIGH when pressed)
NOISE_API = "http://noise:5000"

# Distinct colors for Off + Presets 1-4
COLOR_OFF = Color(0, 0, 0)       # Dim warm amber when stopped (change to Color(0, 0, 0) for dark)
PRESET_COLORS = {
    "p1": Color(0, 120, 255),     # Preset 1: Ocean Blue
    "p2": Color(0, 200, 80),      # Preset 2: Emerald Green
    "p3": Color(150, 40, 255),    # Preset 3: Soft Violet
    "p4": Color(255, 80, 20),     # Preset 4: Sunset Coral
}

strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

r = redis.Redis(host="redis", port=6379, decode_responses=True)
button = Button(BUTTON_PIN, pull_up=None, active_state=False, bounce_time=0.05)

current_step = -1   # -1 = Off, 0..N-1 = Active preset index
held_triggered = False

def set_ring_color(color):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    strip.show()

def get_active_presets():
    """Fetch assigned presets p1..p4 from Redis."""
    keys = ["p1", "p2", "p3", "p4"]
    values = r.mget(keys)
    return [(k, v) for k, v in zip(keys, values) if v]

def stop_sound():
    global current_step
    try:
        requests.post(f"{NOISE_API}/stop/", timeout=2)
    except Exception as e:
        print("Error stopping sound:", e)
    current_step = -1
    set_ring_color(COLOR_OFF)
    print("Playback stopped (OFF)")

def play_preset(key, filename):
    try:
        requests.post(f"{NOISE_API}/play/{filename}/", timeout=2)
        set_ring_color(PRESET_COLORS.get(key, Color(0, 120, 255)))
        print(f"Playing {key}: {filename}")
    except Exception as e:
        print("Error playing preset:", e)

def on_button_release():
    global current_step, held_triggered
    if held_triggered:
        held_triggered = False
        return

    presets = get_active_presets()
    if not presets:
        print("No presets (1-4) saved in web interface yet.")
        return

    # Cycle: Off -> Preset 1 -> Preset 2 -> ... -> Off
    next_step = current_step + 1
    if next_step >= len(presets):
        stop_sound()
    else:
        current_step = next_step
        key, filename = presets[current_step]
        play_preset(key, filename)

def on_button_hold():
    global held_triggered
    held_triggered = True
    stop_sound()

button.hold_time = 1.5
button.when_held = on_button_hold
button.when_released = on_button_release

# Set initial Off state LED color
set_ring_color(COLOR_OFF)

while True:
    time.sleep(0.5)
