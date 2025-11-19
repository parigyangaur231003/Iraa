#!/usr/bin/env python3
"""
Quick audio test script for Iraa
Tests microphone input and speaker output
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

print("Testing Iraa audio components...")
print("-" * 50)

# Test 1: Import audio modules
print("\n1. Testing imports...")
try:
    from speech_io import record_to_wav, transcribe_wav, speak
    print(" Audio modules imported successfully")
except Exception as e:
    print(f" Import failed: {e}")
    sys.exit(1)

# Test 2: Test TTS
print("\n2. Testing Text-to-Speech...")
try:
    speak("Hello, this is a test. Can you hear me?")
    print(" TTS working")
except Exception as e:
    print(f" TTS failed: {e}")

# Test 3: List audio devices
print("\n3. Testing audio devices...")
try:
    import sounddevice as sd
    devices = sd.query_devices()
    inputs = [(i, d['name']) for i, d in enumerate(devices) if d.get('max_input_channels', 0) > 0]
    if inputs:
        print(f" Found {len(inputs)} input device(s):")
        for idx, name in inputs[:3]:
            print(f"   [{idx}] {name}")
    else:
        print("  No input devices found!")
except Exception as e:
    print(f" Device listing failed: {e}")

# Test 4: Test recording (short 2-second test)
print("\n4. Testing microphone recording (2 seconds)...")
import tempfile
try:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_file = f.name
    print("     Speaking now...")
    record_to_wav(tmp_file, seconds=2)
    print(" Recording completed")
    
    # Clean up
    try:
        os.unlink(tmp_file)
    except:
        pass
except Exception as e:
    print(f" Recording failed: {e}")

# Test 5: Test transcription (if we have a file)
print("\n5. Testing speech recognition...")
try:
    # Create a silent test file
    import numpy as np
    import scipy.io.wavfile as wav
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_file = f.name
    # Create silent audio
    data = np.zeros(16000 * 2, dtype=np.int16)  # 2 seconds of silence
    wav.write(tmp_file, 16000, data)
    result = transcribe_wav(tmp_file)
    print(f" Transcription working (got: '{result.get('text', '')}')")
    try:
        os.unlink(tmp_file)
    except:
        pass
except Exception as e:
    print(f" Transcription failed: {e}")

# Test 6: Database connection
print("\n6. Testing database connection...")
try:
    from db import conn
    with conn() as c:
        print(" Database connection successful")
except Exception as e:
    print(f" Database connection failed: {e}")
    print("   (This is OK if database isn't set up yet)")

print("\n" + "-" * 50)
print("Audio test complete!")
print("\nTo run the full app: pipenv run python app.py")

