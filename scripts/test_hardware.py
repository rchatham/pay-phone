#!/usr/bin/env python3
"""
Hardware testing script for payphone components
"""
import sys
import time
import serial
import pygame
import os

def test_serial_connection():
    """Test Arduino serial communication"""
    print("\n=== Testing Serial Connection ===")
    try:
        ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=2)
        time.sleep(2)  # Wait for Arduino reset
        
        # Check for READY signal
        if ser.in_waiting:
            data = ser.readline().decode().strip()
            if data == "READY":
                print("✓ Arduino connected and ready")
            else:
                print(f"✗ Unexpected response: {data}")
        else:
            print("✗ No response from Arduino")
            
        ser.close()
        return True
    except Exception as e:
        print(f"✗ Serial connection failed: {e}")
        return False

def test_keypad():
    """Test keypad input"""
    print("\n=== Testing Keypad ===")
    print("Press each key (0-9, *, #) - Press 'q' to quit")
    
    try:
        ser = serial.Serial('/dev/ttyUSB0', 9600)
        time.sleep(2)
        
        keys_pressed = set()
        expected_keys = set('0123456789*#')
        
        while keys_pressed != expected_keys:
            if ser.in_waiting:
                data = ser.readline().decode().strip()
                if data.startswith("KEY:"):
                    key = data.split(":")[1]
                    keys_pressed.add(key)
                    print(f"✓ Key pressed: {key}")
                    print(f"   Remaining: {expected_keys - keys_pressed}")
                    
        print("✓ All keys tested successfully")
        ser.close()
        return True
    except Exception as e:
        print(f"✗ Keypad test failed: {e}")
        return False

def test_hook_switch():
    """Test hook switch"""
    print("\n=== Testing Hook Switch ===")
    print("Pick up and hang up the handset...")
    
    try:
        ser = serial.Serial('/dev/ttyUSB0', 9600)
        time.sleep(2)
        
        states_seen = set()
        
        while len(states_seen) < 2:
            if ser.in_waiting:
                data = ser.readline().decode().strip()
                if data.startswith("HOOK:"):
                    state = data.split(":")[1]
                    states_seen.add(state)
                    print(f"✓ Hook state: {state}")
                    
        print("✓ Hook switch working")
        ser.close()
        return True
    except Exception as e:
        print(f"✗ Hook switch test failed: {e}")
        return False

def test_audio_output():
    """Test audio output"""
    print("\n=== Testing Audio Output ===")
    
    try:
        pygame.mixer.init()
        
        # Generate test tone
        sample_rate = 44100
        duration = 2
        frequency = 440  # A4 note
        
        import numpy as np
        samples = np.sin(2 * np.pi * frequency * np.arange(sample_rate * duration) / sample_rate)
        samples = (samples * 32767).astype(np.int16)
        
        sound = pygame.sndarray.make_sound(samples)
        print("Playing test tone (440Hz)...")
        sound.play()
        time.sleep(duration)
        
        print("✓ Audio output working")
        return True
    except Exception as e:
        print(f"✗ Audio test failed: {e}")
        return False

def test_microphone():
    """Test microphone recording"""
    print("\n=== Testing Microphone ===")
    print("Speak into the handset for 3 seconds...")
    
    try:
        os.system("arecord -d 3 -f cd test_recording.wav")
        
        if os.path.exists("test_recording.wav"):
            print("✓ Recording created")
            print("Playing back recording...")
            os.system("aplay test_recording.wav")
            
            response = input("Did you hear the playback clearly? (y/n): ")
            os.remove("test_recording.wav")
            return response.lower() == 'y'
        else:
            print("✗ Recording failed")
            return False
    except Exception as e:
        print(f"✗ Microphone test failed: {e}")
        return False

def main():
    """Run all hardware tests"""
    print("=== Payphone Hardware Test Suite ===")
    
    tests = [
        ("Serial Connection", test_serial_connection),
        ("Keypad", test_keypad),
        ("Hook Switch", test_hook_switch),
        ("Audio Output", test_audio_output),
        ("Microphone", test_microphone)
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except KeyboardInterrupt:
            print("\nTest interrupted")
            break
        except Exception as e:
            print(f"Test {name} crashed: {e}")
            results[name] = False
            
    # Summary
    print("\n=== Test Summary ===")
    for name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{name}: {status}")
        
    all_passed = all(results.values())
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())