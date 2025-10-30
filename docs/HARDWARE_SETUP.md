# Hardware Setup Guide

## Wiring Diagram

### Handset Connections
- **Speaker**: Yellow (Signal), Black (Ground)
- **Microphone**: Green (Signal), Red (Power)

### Arduino to Keypad Matrix
- Row pins: D9, D8, D7, D6
- Column pins: D5, D4, D3
- Hook switch: D2 (with pull-up resistor)

### Audio Connections
1. Audio Injector to Handset:
   - Line Out → Amplifier → Handset Speaker
   - Handset Mic → Preamp → Line In

2. Alternative USB Sound Card:
   - Use TRRS splitter for separate mic/speaker

## Circuit Diagrams
[Include actual circuit diagrams here]

## Testing Procedures
1. Use multimeter to verify connections
2. Test continuity on all wires
3. Verify voltage levels (3.3V/5V)