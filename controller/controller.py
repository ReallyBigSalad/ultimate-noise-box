import time
import redis
import requests
from gpiozero import Button
from rpi_ws281x import PixelStrip, Color

# Kano Light Circle HAT Pinout
LED_COUNT = 10
LED_PIN = 18          # GPIO 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 10   # 0-255
LED_INVERT = False
LED_CHANNEL = 0

BUTTON_PIN = 3        # GPIO 3
NOISE_API = "http://noise:5000"
LED_TIMEOUT = 10.0    # Turn off LEDs after 10 seconds with no button press

# Colors: Completely off when stopped/timed out + distinct colors for Presets 1-4
COLOR_OFF = Color(0, 0, 0)
COLOR_WEB_DEFAULT = Color(0, 180, 220)
PRESET_COLORS = {
    "p1": Color(0, 120, 255),           # Preset 1: Ocean Blue
    "p2": Color(0, 200, 80),            # Preset 2: Emerald Green
    "p3": Color(150, 40, 255),          # Preset 3: Soft Violet
    "p4": Color(255, 80, 20),           # Preset 4: Sunset Coral
}

strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

r = redis.Redis(host="redis", port=6379, decode_responses=True)
button = Button(BUTTON_PIN, pull_up=None, active_state=False, bounce_time=0.05)

current_step = -1
held_triggered = False
last_state = None
last_activity = 0.0
leds_on = False

def set_ring_color(color):
    global leds_on
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    strip.show()
    leds_on = (color != COLOR_OFF)

def get_active_presets():
    keys = ["p1", "p2", "p3", "p4"]
    values = r.mget(keys)
    return [(k, v) for k, v in zip(keys, values) if v]

def stop_sound():
    global current_step, last_state
    try:
        requests.post(f"{NOISE_API}/stop/", timeout=2)
    except Exception as e:
        print("Error stopping sound:", e)
    current_step = -1
    last_state = "off"
    r.set("playback_state", "off")
    set_ring_color(COLOR_OFF)
    print("Playback stopped (OFF)")

def play_preset(key, filename):
    global last_state, last_activity
    try:
        requests.post(f"{NOISE_API}/play/{filename}/", timeout=2)
        last_state = filename
        r.set("playback_state", filename)
        set_ring_color(PRESET_COLORS.get(key, COLOR_WEB_DEFAULT))
        last_activity = time.monotonic()
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

    # Cycle continuously: Preset 1 -> Preset 2 -> Preset 3 -> Preset 4 -> Preset 1
    current_step = (current_step + 1) % len(presets)
    key, filename = presets[current_step]
    play_preset(key, filename)

def on_button_hold():
    global held_triggered
    held_triggered = True
    stop_sound()

button.hold_time = 1.5
button.when_held = on_button_hold
button.when_released = on_button_release

# Start with LEDs completely off
r.set("playback_state", "off")
set_ring_color(COLOR_OFF)

while True:
    try:
        state = r.get("playback_state")
        if state and state != last_state:
            last_state = state
            if state == "off":
                current_step = -1
                set_ring_color(COLOR_OFF)
                print("Web UI stopped playback -> LEDs OFF")
            else:
                matched_key = next((k for k, v in get_active_presets() if v == state), None)
                set_ring_color(PRESET_COLORS.get(matched_key, COLOR_WEB_DEFAULT))
                last_activity = time.monotonic()
                print(f"Web UI playing {state} -> LEDs ON")

        # Turn off LEDs after 10 seconds of inactivity (while audio keeps playing)
        if leds_on and (time.monotonic() - last_activity >= LED_TIMEOUT):
            set_ring_color(COLOR_OFF)
            print("10s inactivity timeout -> LEDs OFF")
    except Exception as e:
        print("Loop error:", e)
    time.sleep(0.25)
