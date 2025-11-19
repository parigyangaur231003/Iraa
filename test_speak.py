#!/usr/bin/env python3
"""Quick test to verify speak function is working"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

print("Testing Iraa speak function...")
print("-" * 50)

try:
    from speech_io import speak
    print(" Imported speak function")
except Exception as e:
    print(f" Failed to import: {e}")
    sys.exit(1)

print("\n1. Testing basic speak...")
try:
    speak("Hello, this is a test.")
    print(" Basic speak worked")
except Exception as e:
    print(f" Speak failed: {e}")

print("\n2. Testing multiple phrases...")
try:
    speak("Testing phrase one.")
    speak("Testing phrase two.")
    speak("Testing phrase three.")
    print(" Multiple speaks worked")
except Exception as e:
    print(f" Multiple speaks failed: {e}")

print("\n3. Testing from agent handlers...")
try:
    from agent import handle_time, handle_joke, handle_smalltalk
    print(" Imported handlers")
    
    handle_time(speak)
    print(" handle_time worked")
    
    handle_smalltalk(speak, "hello")
    print(" handle_smalltalk worked")
    
    handle_joke(speak)
    print(" handle_joke worked")
except Exception as e:
    print(f" Handler test failed: {e}")

print("\n" + "-" * 50)
print("Speak test complete!")

