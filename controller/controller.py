import time
import phatbeat
import redis
import requests

NOISE_API = "http://noise:5000"
LED_TIMEOUT = 10.0         # Turn off all LEDs after 10s of inactivity
VOLUME_BAR_DURATION = 1.5  # Show volume bar for 1.5s after pressing Vol+/Vol-

phatbeat.set_brightness(0.04)  # Minimum APA102 hardware brightness (1/31)

# Ultra-dim RGB colors for Off + Presets 1-4
COLOR_OFF = (0, 0, 0)
COLOR_WEB_DEFAULT = (0, 15, 20)
PRESET_COLORS = {
    "p1": (0, 12, 25),       # Preset 1: Dim Ocean Blue
    "p2": (0, 20, 8),        # Preset 2: Dim Emerald Green
    "p3": (15, 4, 25),       # Preset 3: Dim Soft Violet
    "p4": (25, 8, 2),        # Preset 4: Dim Sunset Coral
}

r = redis.Redis(host="redis", port=6379, decode_responses=True)

current_step = 0
current_volume = 100
current_preset_color = COLOR_OFF
last_state = None
last_activity = 0.0
volume_display_until = 0.0
leds_on = False

def set_ring_color(rgb):
    global leds_on
    r_val, g_val, b_val = rgb
    phatbeat.set_all(r_val, g_val, b_val)
    phatbeat.show()
    leds_on = (rgb != COLOR_OFF)

def show_volume_bar(volume_pct):
    """Light both 8-LED rows from bottom to top proportionally to volume (0-100%)."""
    global leds_on
    lit_count = round((volume_pct / 100.0) * 8)
    phatbeat.clear()
    for i in range(lit_count):
        if i < 5:
            color = (0, 20, 8)       # Bottom 5 LEDs (0-62%)
        elif i < 7:
            color = (25, 16, 0)      # Middle 2 LEDs (63-87%)
        else:
            color = (25, 4, 2)       # Top LED (88-100%)
        # Fill from bottom (7 & 15) up to top (0 & 8)
        phatbeat.set_pixel(7 - i, *color)
        phatbeat.set_pixel(15 - i, *color)
    phatbeat.show()
    leds_on = True

def get_active_presets():
    keys = ["p1", "p2", "p3", "p4"]
    values = r.mget(keys)
    return [(k, v) for k, v in zip(keys, values) if v]

def stop_sound():
    global last_state, current_preset_color, volume_display_until
    try:
        requests.post(f"{NOISE_API}/stop/", timeout=2)
    except Exception as e:
        print("Error stopping sound:", e)
    last_state = "off"
    current_preset_color = COLOR_OFF
    volume_display_until = 0.0
    r.set("playback_state", "off")
    set_ring_color(COLOR_OFF)

def play_preset(key, filename):
    global last_state, last_activity, current_preset_color, volume_display_until
    try:
        requests.post(f"{NOISE_API}/play/{filename}/", timeout=2)
        last_state = filename
        r.set("playback_state", filename)
        current_preset_color = PRESET_COLORS.get(key, COLOR_WEB_DEFAULT)
        volume_display_until = 0.0
        set_ring_color(current_preset_color)
        last_activity = time.monotonic()
    except Exception as e:
        print("Error playing preset:", e)

def change_volume(delta):
    global current_volume, last_activity, volume_display_until
    current_volume = max(0, min(100, current_volume + delta))
    try:
        requests.post(f"{NOISE_API}/volume/{current_volume}/", timeout=2)
        now = time.monotonic()
        last_activity = now
        volume_display_until = now + VOLUME_BAR_DURATION
        show_volume_bar(current_volume)
        print(f"Volume: {current_volume}%")
    except Exception as e:
        print("Volume error:", e)

# pHAT BEAT Built-in Button Handlers
@phatbeat.on(phatbeat.BTN_FASTFWD)
def handle_ff(pin):
    global current_step
    presets = get_active_presets()
    if not presets:
        return
    current_step = (current_step + 1) % len(presets)
    key, filename = presets[current_step]
    play_preset(key, filename)

@phatbeat.on(phatbeat.BTN_REWIND)
def handle_rew(pin):
    global current_step
    presets = get_active_presets()
    if not presets:
        return
    current_step = (current_step - 1) % len(presets)
    key, filename = presets[current_step]
    play_preset(key, filename)

@phatbeat.on(phatbeat.BTN_PLAYPAUSE)
def handle_play(pin):
    global current_step
    if last_state and last_state != "off":
        stop_sound()
    else:
        presets = get_active_presets()
        if presets:
            current_step = current_step % len(presets)
            key, filename = presets[current_step]
            play_preset(key, filename)

@phatbeat.on(phatbeat.BTN_VOLUP)
def handle_vol_up(pin):
    change_volume(10)

@phatbeat.on(phatbeat.BTN_VOLDN)
def handle_vol_dn(pin):
    change_volume(-10)

@phatbeat.on(phatbeat.BTN_ONOFF)
def handle_off(pin):
    stop_sound()

r.set("playback_state", "off")
set_ring_color(COLOR_OFF)

while True:
    try:
        now = time.monotonic()
        state = r.get("playback_state")
        if state and state != last_state:
            last_state = state
            volume_display_until = 0.0
            if state == "off":
                current_preset_color = COLOR_OFF
                set_ring_color(COLOR_OFF)
            else:
                matched_key = next((k for k, v in get_active_presets() if v == state), None)
                current_preset_color = PRESET_COLORS.get(matched_key, COLOR_WEB_DEFAULT)
                set_ring_color(current_preset_color)
                last_activity = now

        # Restore preset color once the 1.5s volume bar finishes
        if volume_display_until > 0 and now >= volume_display_until:
            volume_display_until = 0.0
            set_ring_color(current_preset_color)

        # Turn off all LEDs after 10 seconds of inactivity
        if leds_on and (now - last_activity >= LED_TIMEOUT):
            set_ring_color(COLOR_OFF)
    except Exception as e:
        print("Loop error:", e)
    time.sleep(0.1)
