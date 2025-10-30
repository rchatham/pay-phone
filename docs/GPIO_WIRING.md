# GPIO Direct Wiring Guide

## Overview
This guide explains how to wire the payphone hardware directly to the Raspberry Pi GPIO pins, eliminating the need for an Arduino.

## GPIO Pin Assignments

### Default Pin Configuration

| Component | Function | GPIO Pin | Physical Pin | Wire Color |
|-----------|----------|----------|--------------|------------|
| **Keypad Rows** |
| Row 1 | Keys 1,2,3 | GPIO 5 | Pin 29 | Red |
| Row 2 | Keys 4,5,6 | GPIO 6 | Pin 31 | Orange |
| Row 3 | Keys 7,8,9 | GPIO 13 | Pin 33 | Yellow |
| Row 4 | Keys *,0,# | GPIO 19 | Pin 35 | Green |
| **Keypad Columns** |
| Col 1 | Keys 1,4,7,* | GPIO 26 | Pin 37 | Blue |
| Col 2 | Keys 2,5,8,0 | GPIO 20 | Pin 38 | Purple |
| Col 3 | Keys 3,6,9,# | GPIO 21 | Pin 40 | Gray |
| **Hook Switch** |
| Hook | Handset detect | GPIO 17 | Pin 11 | Black |
| Ground | Common ground | GND | Pin 9 | Brown |

## Wiring Instructions

### 1. Keypad Matrix Wiring

The phone keypad uses a 4x3 matrix configuration:

```
    Col1  Col2  Col3
Row1  1     2     3
Row2  4     5     6  
Row3  7     8     9
Row4  *     0     #
```

**Steps:**
1. Locate the keypad ribbon cable or individual wires
2. Use a multimeter to identify which wires correspond to rows and columns
3. Connect row wires to GPIO row pins (GPIO 5, 6, 13, 19)
4. Connect column wires to GPIO column pins (GPIO 26, 20, 21)
5. No pull-up resistors needed - we use internal pull-ups

### 2. Hook Switch Wiring

The hook switch detects when the handset is lifted:

**Steps:**
1. Locate the two wires from the hook switch
2. Connect one wire to GPIO 17
3. Connect the other wire to GND
4. The switch should close (connect) when handset is on-hook

### 3. Audio Connections

For the handset audio, you still need an audio interface:

**Option 1: Audio Injector**
- Handset Speaker → Audio Injector Line Out (through amplifier)
- Handset Microphone → Audio Injector Line In (through preamp)

**Option 2: USB Sound Card**
- Use a TRRS to dual 3.5mm adapter
- Handset Speaker → Speaker jack (green)
- Handset Microphone → Microphone jack (pink)

## Testing Your Connections

1. **Check GPIO availability:**
   ```bash
   gpio readall
   ```

2. **Test individual pins:**
   ```bash
   # Test hook switch
   gpio -g mode 17 in
   gpio -g read 17  # Should change when lifting handset
   ```

3. **Run hardware test script:**
   ```bash
   python3 scripts/test_hardware_gpio.py
   ```

## Troubleshooting

### Keypad not responding
- Verify row/column assignments with multimeter
- Check for loose connections
- Ensure no shorts between pins

### Hook switch not working
- Verify switch polarity
- Check continuity with multimeter
- Ensure pull-up is enabled in code

### GPIO conflicts
- Check that pins aren't used by other services
- Disable I2C/SPI if using those pins
- Use `raspi-config` to free up GPIO pins

## Alternative Pin Assignments

If default pins conflict with your setup, you can use these alternatives:

```bash
# Set custom pins via environment variables
export KEYPAD_ROW_PINS='[22, 23, 24, 25]'
export KEYPAD_COL_PINS='[7, 8, 11]'
export HOOK_SWITCH_PIN='27'
```

## Safety Notes

⚠️ **Important:**
- Always shutdown Pi before making connections
- Use 3.3V logic levels only - the Pi GPIO is NOT 5V tolerant
- Add 100Ω series resistors for extra protection
- Double-check connections before powering on