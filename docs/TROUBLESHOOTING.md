# Troubleshooting Guide

## Common Issues

### No Serial Communication
- Check USB connection
- Verify Arduino has correct sketch
- Check device permissions: `sudo chmod 666 /dev/ttyUSB0`

### No Audio Output
- Run `alsamixer` and check levels
- Verify Audio Injector is detected: `aplay -l`
- Test with: `speaker-test -c2`

### Microphone Not Working
- Check phantom power if using electret mic
- Verify gain settings in alsamixer
- Test with: `arecord -d 5 test.wav && aplay test.wav`

### Keypad Not Responding
- Check wiring connections
- Verify pull-up resistors
- Test with Arduino serial monitor