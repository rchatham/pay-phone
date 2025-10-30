# GPIO Pin Testing Guide

## Current Status

### ✓ Successfully Mapped (5 of 7 keypad pins):
- **ROW 1**: GPIO 19 (buttons 4, 5, 6)
- **ROW 2**: GPIO 23 (buttons 7, 8, 9)
- **ROW 3**: GPIO 24 (buttons *, 0, #)
- **COL 1**: GPIO 22 (buttons 2, 5, 8, 0)
- **COL 2**: GPIO 20 (buttons 3, 6, 9, #)

### ✗ Missing (2 keypad pins + hook switch):
- **ROW 0**: Unknown (buttons 1, 2, 3)
- **COL 0**: Unknown (buttons 1, 4, 7, *)
- **Hook Switch**: Unknown (1-2 pins)

## Testing Commands

### Test Individual Buttons

To test button 2 (should reveal ROW 0):
```bash
cd /home/pi/payphone
python3 scripts/test_single_button.py 2
# Hold button 2 when prompted
```

To test button 4 (should reveal COL 0):
```bash
python3 scripts/test_single_button.py 4
# Hold button 4 when prompted
```

To test button 1 (requires both ROW 0 and COL 0):
```bash
python3 scripts/test_single_button.py 1
# Hold button 1 when prompted
```

### Expected Results

**Button 2 should show**:
- One pin connecting to GPIO 22 (COL 1)
- That new pin is ROW 0

**Button 4 should show**:
- One pin connecting to GPIO 19 (ROW 1)
- That new pin is COL 0

**Button 1 should show**:
- Connection between ROW 0 and COL 0

## Possible Issues

### If ROW 0 or COL 0 Still Not Detecting:

1. **Check Physical Wiring**:
   - Verify all 14 GPIO pins are actually connected
   - Check for loose connections
   - Verify solder joints

2. **Test Remaining Unused Pins**:
   - Unused pins: [17, 18, 27, 25, 5, 6, 12, 13, 21]
   - One should be ROW 0, another should be COL 0

3. **Keypad Matrix May Be Incomplete**:
   - The keypad might only have partial rows/columns wired
   - May need to add jumper wires for missing connections

### Hook Switch

Test the hook switch separately:
```bash
python3 scripts/simple_pin_viewer.py
```

This will show which pins change when you lift/lower the handset.

## Partial Configuration

If ROW 0 and COL 0 cannot be found, you can still configure a partial keypad:

```bash
# /etc/payphone/.env
KEYPAD_ROW_PINS=[NONE,19,23,24]  # Row 0 missing
KEYPAD_COL_PINS=[NONE,22,20]     # Col 0 missing
```

This gives you buttons: 5, 6, 8, 9, 0, # (6 of 12 buttons)

## Next Steps

1. Run the button tests manually while at the terminal
2. Document which pins are found for ROW 0 and COL 0
3. Update the configuration file
4. Test the complete keypad
