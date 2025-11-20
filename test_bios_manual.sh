#!/bin/bash
# Manual BIOS test - simulates user keypresses

echo "Starting BIOS test with simulated keypresses..."
echo ""
echo "Inputs:"
echo "  4  - Select BIOS mode"
echo "  y  - Silent mode"
echo "  1  - Select Information Booth"
echo "  1  - Select Info submenu"
echo "  q  - Quit"
echo ""

python3 test_phone_tree.py <<EOF
4
y
1
1
q
EOF
