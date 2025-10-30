import os
import json

class Config:
    # Hardware mode selection
    USE_GPIO = os.getenv('USE_GPIO', 'true').lower() == 'true'
    
    # Serial communication (for Arduino mode)
    SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
    BAUDRATE = int(os.getenv('BAUDRATE', '9600'))
    
    # GPIO pins (for direct Raspberry Pi connection)
    # Keypad matrix pins
    KEYPAD_ROW_PINS = json.loads(os.getenv('KEYPAD_ROW_PINS', '[5, 6, 13, 19]'))  # GPIO pins for rows
    KEYPAD_COL_PINS = json.loads(os.getenv('KEYPAD_COL_PINS', '[26, 20, 21]'))     # GPIO pins for columns

    # Hook switch pin(s)
    # Supports both single pin (HOOK_SWITCH_PIN) and dual pin (HOOK_SWITCH_PINS)
    if os.getenv('HOOK_SWITCH_PINS'):
        # 2-pin mode: two GPIO pins that connect/disconnect
        HOOK_SWITCH_PIN = json.loads(os.getenv('HOOK_SWITCH_PINS'))
    else:
        # 1-pin mode: single GPIO pin with other side connected to GND
        HOOK_SWITCH_PIN = int(os.getenv('HOOK_SWITCH_PIN', '17'))
    
    # Audio settings
    AUDIO_DIR = os.getenv('AUDIO_DIR', 'audio_files')
    SAMPLE_RATE = int(os.getenv('SAMPLE_RATE', '44100'))
    
    # Phone tree settings
    MENU_TIMEOUT = int(os.getenv('MENU_TIMEOUT', '30'))
    
    # Features
    ENABLE_RECORDING = os.getenv('ENABLE_RECORDING', 'false').lower() == 'true'
    ENABLE_CELLULAR = os.getenv('ENABLE_CELLULAR', 'false').lower() == 'true'