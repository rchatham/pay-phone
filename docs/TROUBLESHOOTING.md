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
- Install recording dependencies: `sudo apt-get install -y portaudio19-dev libsndfile1 alsa-utils`
- Check phantom power if using electret mic
- Verify gain settings in `alsamixer`
- List ALSA devices: `arecord -l`
- List PortAudio devices: `python -m sounddevice`
- Test raw ALSA capture: `arecord --device=hw:0,0 --format S16_LE -V mono --rate 44100 -c1 test.wav && aplay test.wav`
- Test LAM capture: `ENABLE_RECORDING=true RECORDING_DEVICE=0 python scripts/test_lam_recording.py`
- `RECORDING_DEVICE` may be unset for auto/default input, an integer device index, or a case-insensitive device name fragment.
- If LAM says recording is unavailable, check `ENABLE_RECORDING=true`, the Python dependencies `sounddevice` and `soundfile`, and whether `sounddevice.query_devices(kind="input")` returns an input-capable device.

### Keypad Not Responding
- Check wiring connections
- Verify pull-up resistors
- Test with Arduino serial monitor