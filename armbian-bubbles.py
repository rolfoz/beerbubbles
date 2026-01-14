#This version works on an Orange Pi Zero or similar running armbian with a USB to audio adapter and a microphone plugged in.

import time
import subprocess
import os
import numpy as np
import wave
from scipy.signal import butter, lfilter
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

# ────────────────────────────────────────────────
#                 CONFIGURATION
# ────────────────────────────────────────────────
MQTT_HOST      = ""
MQTT_TOPIC     = "homeassistant/sensor/beerbubbles"
MQTT_USER      = ""
MQTT_PASS      = ""

RECORD_DURATION = 10
PROCESS_FILE    = "process.wav"

# ALSA Device for USB Mic. 
# Use 'arecord -l' to confirm. Usually hw:1,0 for USB adapters.
ALSA_DEVICE     = "hw:0,0" 

# ────────────────────────────────────────────────
#            ADAPTIVE DETECTION ENGINE
# ────────────────────────────────────────────────

def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut/nyq, highcut/nyq], btype='band')
    return b, a

def count_bubbles_v22(audio, sr):
    if len(audio) == 0: return 0, 0
    
    # 1. ISOLATE THE POP (Ignore compressor hum < 400Hz)
    b, a = butter_bandpass(400, 3000, sr)
    filtered = lfilter(b, a, audio - np.mean(audio))
    
    # 2. CREATE ENVELOPE
    envelope = np.sqrt(np.convolve(filtered**2, np.ones(10)/10, mode='same'))
    
    # 3. DYNAMIC NOISE FLOOR
    baseline_win = int(0.5 * sr)
    noise_floor = np.convolve(envelope, np.ones(baseline_win)/baseline_win, mode='same')
    
    # 4. SIGNAL-TO-NOISE EXTRACTION
    snr_signal = np.maximum(envelope - noise_floor, 0)
    
    # 5. AUTO-GAIN
    max_peak = np.max(snr_signal)
    if max_peak > 0.0001:
        norm_signal = snr_signal / max_peak
    else:
        return 0, 0

    # 6. SCHMITT TRIGGER
    high_thresh = 0.4 
    low_thresh  = 0.1 
    min_gap = int(0.08 * sr) 

    count = 0
    is_active = False
    last_sample = 0
    for i, val in enumerate(norm_signal):
        if not is_active:
            if val > high_thresh and (i - last_sample) > min_gap:
                is_active = True
                count += 1
                last_sample = i
        else:
            if val < low_thresh:
                is_active = False
                
    return count, max_peak

# ────────────────────────────────────────────────
#                 MAIN LOOP
# ────────────────────────────────────────────────

print(f"V22: Starting Armbian Bubble Lock on {ALSA_DEVICE}...")

while True:
    if os.path.exists(PROCESS_FILE): os.remove(PROCESS_FILE)

    print(f"\n--- Recording {RECORD_DURATION}s ---")
    
    # arecord: -D (Device), -d (Duration), -f (Format), -r (Rate), -c (Channels)
    # S16_LE is standard 16-bit little endian
    try:
        subprocess.run([
            "arecord", 
            "-D", ALSA_DEVICE, 
            "-d", str(RECORD_DURATION), 
            "-f", "S16_LE", 
            "-r", "8000", 
            "-c", "1", 
            PROCESS_FILE
        ], check=True, capture_output=True)

        if os.path.exists(PROCESS_FILE) and os.path.getsize(PROCESS_FILE) > 100:
            with wave.open(PROCESS_FILE, 'rb') as wf:
                sr = wf.getframerate()
                samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
            
            bubbles, signal_strength = count_bubbles_v22(samples, sr)
            bpm = int(bubbles * (60 / RECORD_DURATION))
            
            print(f"Strength: {signal_strength:.5f} | Bubbles: {bubbles} | BPM: {bpm}")

            if signal_strength > 0.0005: 
                client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.publish(MQTT_TOPIC, str(bpm))
                client.disconnect()
            else:
                print("No signal locked. Tuning gain or check mic placement.")

        else:
            print("Recording failed. Audio file is empty.")

    except subprocess.CalledProcessError as e:
        print(f"ALSA Error: {e}. Is the USB mic plugged in?")
    except Exception as e:
        print(f"Error: {e}")

    # Wait before next cycle
    time.sleep(50)
