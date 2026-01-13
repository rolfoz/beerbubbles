#Get an old android phone
#install LineageOS on it
#Root it with Magisk
#Install Termux and Termux API and Termux Boot
#Give Termux root permissions (just sudo in it)
#Give Termux API all Andoid permissions
#pkg install python termux-api mosquitto
#pkg install tur-repo     # Adds the TUR repository
#pkg update               # Refresh package lists
#pkg install python-scipy # Installs scipy
#pkg install python-numpy

#You may want to install sshd so you can remotely get into your phone to mess with things.
#Use termux boot to create a startup script that will run this on boot.
#you have an automatic bubble counter that will publish to homeassistant over mqtt


import time
import subprocess
import os
import numpy as np
import wave
from scipy.signal import butter, lfilter
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

# ────────────────────────────────────────────────
#                CONFIGURATION
# ────────────────────────────────────────────────
MQTT_HOST     = ""
MQTT_TOPIC    = "homeassistant/sensor/beerbubbles"
MQTT_USER     = ""
MQTT_PASS     = ""

RECORD_DURATION = 10
RECORD_FILE     = "bubbles.wav"

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
    
    # 3. DYNAMIC NOISE FLOOR (Tracks compressor kick-ins)
    # We use a 500ms moving average to define "silence"
    baseline_win = int(0.5 * sr)
    noise_floor = np.convolve(envelope, np.ones(baseline_win)/baseline_win, mode='same')
    
    # 4. SIGNAL-TO-NOISE EXTRACTION
    # This makes the bubbles stand out even if the background gets louder
    snr_signal = np.maximum(envelope - noise_floor, 0)
    
    # 5. AUTO-GAIN (Adaptive Scaling)
    # Scale the highest spike to 1.0. If silence, this won't do much.
    max_peak = np.max(snr_signal)
    if max_peak > 0.0001:
        norm_signal = snr_signal / max_peak
    else:
        return 0, 0

    # 6. SCHMITT TRIGGER (Lock-on logic)
    # Higher threshold (0.4) ensures it's a real pop, not just hiss.
    high_thresh = 0.4 
    low_thresh  = 0.1 
    min_gap = int(0.08 * sr) # 80ms lockout (prevents double counting up to 750 BPM)

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
#                MAIN LOOP
# ────────────────────────────────────────────────

print("V22: Starting Adaptive Bubble Lock (6-600 BPM range)...")

while True:
    if os.path.exists(RECORD_FILE): os.remove(RECORD_FILE)
    
    # Record using the most stable Termux encoder
    print(f"\n--- Recording {RECORD_DURATION}s ---")
    subprocess.run(["termux-microphone-record", "-f", RECORD_FILE, "-l", str(RECORD_DURATION)])
    
    # Wait for file to close
    time.sleep(RECORD_DURATION + 1)
    subprocess.run(["termux-microphone-record", "-q"], capture_output=True)

    if os.path.exists(RECORD_FILE) and os.path.getsize(RECORD_FILE) > 100:
        try:
            # We use FFmpeg to convert the result to a predictable format for Python
            # This solves the "RIFF ID" and 0-byte raw issues once and for all
            subprocess.run(["ffmpeg", "-y", "-i", RECORD_FILE, "-ar", "8000", "-ac", "1", "process.wav"], capture_output=True)
            
            with wave.open("process.wav", 'rb') as wf:
                sr = wf.getframerate()
                samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
            
            bubbles, signal_strength = count_bubbles_v22(samples, sr)
            bpm = int(bubbles * (60 / RECORD_DURATION))
            
            print(f"Strength: {signal_strength:.5f} | Bubbles: {bubbles} | BPM: {bpm}")

            if signal_strength > 0.0005: # "Locked" signal
                client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.publish(MQTT_TOPIC, str(bpm))
                client.disconnect()
            else:
                print("No signal locked. Tuning gain for next pass...")

        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Recording failed. Check Termux Mic Permissions!")

    time.sleep(50)
