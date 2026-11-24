import time
import phatbeat
import redis
import requests
from gpiozero import Button

NOISE_API = "http://noise:5000"
LED_TIMEOUT = 10.0

# RGB colors for Off + Presets 1-4
COLOR_OFF = (0, 0, 0)
COLOR_WEB_DEFAULT = (0, 180, 220)
PRESET_COLORS = {
    "p1": (0, 120, 255),     # Preset 1: Ocean Blue
    "p2": (0, 200, 80),      # Preset 2: Emerald Green
    "p3": (150, 40, 255),    # Preset 3: Soft Violet
    "p4": (255, 80, 20),     # Preset 4: Sunset Coral
}

# pHAT BEAT 6 Edge Buttons (all active-low with internal pull-ups)
btn_ff = Button(5, pull_up=True, bounce_time=0.05)       # Next preset
btn_rew = Button(13, pull_up=True, bounce_time=0.05)     # Previous preset
btn_play = Button(6, pull_up=True, bounce_time=0.05)     # Play / Stop toggle
btn_vol_up = Button(16, pull_up=True, bounce_time=0.05)  # Volume +10
btn_vol_dn = Button(26, pull_up=True, bounce_time=0.05)  # Volume -10
btn_off = Button(12, pull_up=True, bounce_time=0.05)     # Stop playback

phatbeat.set_brightness(0.15)  # 0.0 to 1.0 (dim nighttime level)
r = redis.Redis(host="redis", port=6379, decode_responses=True)

current_step = 0
current_volume = 100
last_state = None
last_activity = 0.0
leds_on = False

def set_ring_color(rgb):
    global leds_on
    r_val, g_val, b_val = rgb
    phatbeat.set_all(r_val, g_val, b_val)
    phatbeat.show()
    leds_on = (rgb != COLOR_OFF)

def get_active_presets():
    keys = ["p1", "p2", "p3", "p4"]
    values = r.mget(keys)
    return [(k, v) for k, v in zip(keys, values) if v]

def stop_sound():
    global last_state
    try:
        requests.post(f"{NOISE_API}/stop/", timeout=2)
    except Exception as e:
        print("Error stopping sound:", e)
    last_state = "off"
    r.set("playback_state", "off")
    set_ring_color(COLOR_OFF)

def play_preset(key, filename):
    global last_state, last_activity
    try:
        requests.post(f"{NOISE_API}/play/{filename}/", timeout=2)
        last_state = filename
        r.set("playback_state", filename)
        set_ring_color(PRESET_COLORS.get(key, COLOR_WEB_DEFAULT))
        last_activity = time.monotonic()
    except Exception as e:
        print("Error playing preset:", e)

def next_preset():
    global current_step
    presets = get_active_presets()
    if not presets:
        return
    current_step = (current_step + 1) % len(presets)
    key, filename = presets[current_step]
    play_preset(key, filename)

def prev_preset():
    global current_step
    presets = get_active_presets()
    if not presets:
        return
    current_step = (current_step - 1) % len(presets)
    key, filename = presets[current_step]
    play_preset(key, filename)

def toggle_play():
    global current_step
    if last_state and last_state != "off":
        stop_sound()
    else:
        presets = get_active_presets()
        if presets:
            current_step = current_step % len(presets)
            key, filename = presets[current_step]
            play_preset(key, filename)

def change_volume(delta):
    global current_volume, last_activity
    current_volume = max(0, min(100, current_volume + delta))
    try:
        requests.post(f"{NOISE_API}/volume/{current_volume}/", timeout=2)
        last_activity = time.monotonic()
        print(f"Volume: {current_volume}%")
    except Exception as e:
        print("Volume error:", e)

btn_ff.when_pressed = next_preset
btn_rew.when_pressed = prev_preset
btn_play.when_pressed = toggle_play
btn_vol_up.when_pressed = lambda: change_volume(10)
btn_vol_dn.when_pressed = lambda: change_volume(-10)
btn_off.when_pressed = stop_sound

r.set("playback_state", "off")
set_ring_color(COLOR_OFF)

while True:
    try:
        state = r.get("playback_state")
        if state and state != last_state:
            last_state = state
            if state == "off":
                set_ring_color(COLOR_OFF)
            else:
                matched_key = next((k for k, v in get_active_presets() if v == state), None)
                set_ring_color(PRESET_COLORS.get(matched_key, COLOR_WEB_DEFAULT))
                last_activity = time.monotonic()

        if leds_on and (time.monotonic() - last_activity >= LED_TIMEOUT):
            set_ring_color(COLOR_OFF)
    except Exception as e:
        print("Loop error:", e)
    time.sleep(0.25)
