#!/usr/bin/env python3
"""
Hardware testing script for GPIO-connected payphone components
"""
import sys
import time
import pygame
import os

# Check if running on Raspberry Pi
try:
    import RPi.GPIO as GPIO
    ON_PI = True
except ImportError:
    print("Warning: RPi.GPIO not available. Some tests will be skipped.")
    ON_PI = False

# Default pin configuration
KEYPAD_ROW_PINS = [5, 6, 13, 19]
KEYPAD_COL_PINS = [26, 20, 21]
HOOK_SWITCH_PIN = 17

def test_gpio_available():
    """Test if GPIO is available and accessible"""
    print("\n=== Testing GPIO Availability ===")
    
    if not ON_PI:
        print("✗ Not running on Raspberry Pi")
        return False
        
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        print("✓ GPIO library loaded successfully")
        GPIO.cleanup()
        return True
    except Exception as e:
        print(f"✗ GPIO initialization failed: {e}")
        print("  Try running with sudo: sudo python3 test_hardware_gpio.py")
        return False

def test_keypad_gpio():
    """Test keypad matrix using GPIO"""
    print("\n=== Testing Keypad (GPIO) ===")
    
    if not ON_PI:
        print("✗ Skipping - not on Raspberry Pi")
        return False
        
    try:
        GPIO.setmode(GPIO.BCM)
        
        # Setup pins
        for pin in KEYPAD_ROW_PINS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            
        for pin in KEYPAD_COL_PINS:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
        print("GPIO pins configured for keypad")
        print(f"Row pins: {KEYPAD_ROW_PINS}")
        print(f"Column pins: {KEYPAD_COL_PINS}")
        print("\nPress each key (0-9, *, #) - Press Ctrl+C when done")
        
        keys = [
            ['1', '2', '3'],
            ['4', '5', '6'],
            ['7', '8', '9'],
            ['*', '0', '#']
        ]
        
        keys_pressed = set()
        expected_keys = set('0123456789*#')
        last_key = None
        
        while keys_pressed != expected_keys:
            for row_num, row_pin in enumerate(KEYPAD_ROW_PINS):
                GPIO.output(row_pin, GPIO.LOW)
                
                for col_num, col_pin in enumerate(KEYPAD_COL_PINS):
                    if GPIO.input(col_pin) == GPIO.LOW:
                        key = keys[row_num][col_num]
                        if key != last_key:
                            keys_pressed.add(key)
                            print(f"✓ Key pressed: {key}")
                            print(f"   Remaining: {expected_keys - keys_pressed}")
                            last_key = key
                            
                GPIO.output(row_pin, GPIO.HIGH)
                
            time.sleep(0.01)
            
        print("✓ All keys tested successfully")
        GPIO.cleanup()
        return True
        
    except KeyboardInterrupt:
        print("\n✓ Keypad test completed (interrupted)")
        GPIO.cleanup()
        return True
    except Exception as e:
        print(f"✗ Keypad test failed: {e}")
        GPIO.cleanup()
        return False

def test_hook_switch_gpio():
    """Test hook switch using GPIO"""
    print("\n=== Testing Hook Switch (GPIO) ===")
    
    if not ON_PI:
        print("✗ Skipping - not on Raspberry Pi")
        return False
        
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(HOOK_SWITCH_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        print(f"Hook switch configured on GPIO {HOOK_SWITCH_PIN}")
        print("Lift and hang up the handset several times...")
        print("Press Ctrl+C when done")
        
        last_state = None
        states_seen = set()
        
        while len(states_seen) < 2:
            current_state = GPIO.input(HOOK_SWITCH_PIN)
            
            if current_state != last_state:
                state_name = "OFF HOOK" if current_state == GPIO.LOW else "ON HOOK"
                print(f"✓ Hook state: {state_name}")
                states_seen.add(current_state)
                last_state = current_state
                
            time.sleep(0.01)
            
        print("✓ Hook switch working correctly")
        GPIO.cleanup()
        return True
        
    except KeyboardInterrupt:
        print("\n✓ Hook switch test completed")
        GPIO.cleanup()
        return True
    except Exception as e:
        print(f"✗ Hook switch test failed: {e}")
        GPIO.cleanup()
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

def check_pin_conflicts():
    """Check for potential GPIO pin conflicts"""
    print("\n=== Checking GPIO Pin Conflicts ===")
    
    conflicts = []
    
    # Check I2C pins
    i2c_pins = [2, 3]
    used_pins = KEYPAD_ROW_PINS + KEYPAD_COL_PINS + [HOOK_SWITCH_PIN]
    
    for pin in i2c_pins:
        if pin in used_pins:
            conflicts.append(f"GPIO {pin} (I2C)")
            
    # Check SPI pins
    spi_pins = [7, 8, 9, 10, 11]
    for pin in spi_pins:
        if pin in used_pins:
            conflicts.append(f"GPIO {pin} (SPI)")
            
    if conflicts:
        print("⚠️  Potential conflicts detected:")
        for conflict in conflicts:
            print(f"   - {conflict}")
        print("   Disable I2C/SPI in raspi-config if not needed")
    else:
        print("✓ No GPIO conflicts detected")
        
    return len(conflicts) == 0

def main():
    """Run all hardware tests"""
    print("=== Payphone GPIO Hardware Test Suite ===")
    print(f"Configured pins:")
    print(f"  Keypad rows: {KEYPAD_ROW_PINS}")
    print(f"  Keypad cols: {KEYPAD_COL_PINS}")
    print(f"  Hook switch: {HOOK_SWITCH_PIN}")
    
    tests = [
        ("GPIO Availability", test_gpio_available),
        ("Pin Conflicts", check_pin_conflicts),
        ("Hook Switch", test_hook_switch_gpio),
        ("Keypad", test_keypad_gpio),
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
    
    if not all_passed and not ON_PI:
        print("\nNote: Some tests require running on a Raspberry Pi")
        
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())