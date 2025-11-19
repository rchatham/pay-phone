# Extension Mode Audio Prompts

This document describes the audio files required for the extension dialing feature.

## Required Audio Files

### Error Prompts

#### `prompts/invalid_extension.mp3`
**Purpose**: Played when user dials an extension that doesn't exist in the options

**Example Script**:
> "I'm sorry, that extension is not valid. Please try again."

**When Played**:
- User dials a complete extension (either fixed-length or terminator-based) that doesn't match any option key
- Followed by clearing the input queue and replaying the directory/menu prompt

---

### Optional Enhanced Prompts

The following prompts are optional but can improve user experience:

#### `prompts/extension_timeout.mp3` (Future Enhancement)
**Purpose**: Played when extension collection times out due to inactivity

**Example Script**:
> "Your input has timed out. Returning to the main menu."

**Current Behavior**: Uses the existing `prompts/timeout.mp3` file

---

## Menu-Specific Prompts

When implementing extension mode menus, you'll need specific prompts for each menu:

### Employee Directory Example

#### `menu/directory.mp3`
**Example Script**:
> "Employee directory. Please dial the three-digit extension of the person you wish to reach."

#### `directory/alice.mp3`, `directory/bob.mp3`, etc.
**Example Script**:
> "You have reached Alice Smith. Please leave a message after the tone."

### Department Menu Example

#### `menu/departments.mp3`
**Example Script**:
> "Department directory. Dial 10 for Sales, 20 for Support, or 30 for Engineering. Press pound when finished."

#### `departments/sales.mp3`, `departments/support.mp3`, etc.
**Example Script**:
> "You have reached the Sales department. Our office hours are Monday through Friday, 9 AM to 5 PM."

---

## Audio File Organization

Recommended directory structure:

```
audio_files/
├── prompts/
│   ├── dial_tone.mp3
│   ├── timeout.mp3
│   ├── invalid_option.mp3
│   └── invalid_extension.mp3      # NEW - Required for extension mode
├── menu/
│   ├── main_menu.mp3
│   ├── main_menu_ext.mp3         # Example: Main menu for extension-based system
│   ├── directory.mp3               # NEW - Employee directory prompt
│   └── departments.mp3             # NEW - Departments prompt
├── directory/                      # NEW - Employee voicemails/messages
│   ├── alice.mp3
│   ├── bob.mp3
│   ├── charlie.mp3
│   └── diana.mp3
└── departments/                    # NEW - Department messages
    ├── sales.mp3
    ├── support.mp3
    └── engineering.mp3
```

---

## Creating Audio Files

### Using Text-to-Speech

You can use the included `generate_audio.py` script (if available) or online TTS services:

1. **Google Cloud Text-to-Speech**: High quality, natural voices
2. **Amazon Polly**: Good variety of voices and languages
3. **OpenAI TTS**: Very natural-sounding voices
4. **ElevenLabs**: Extremely realistic voices

### Recording Your Own

For a more personal touch:

1. Use a quiet environment
2. Record in WAV format at 44.1kHz, 16-bit, stereo
3. Convert to MP3 at 128kbps or higher
4. Normalize audio levels across all files

### Audio Specifications

- **Format**: MP3
- **Sample Rate**: 44.1kHz (recommended)
- **Bit Rate**: 128kbps or higher
- **Channels**: Mono or Stereo
- **Length**: Keep prompts concise (5-15 seconds)

---

## Extension Mode Configuration Examples

### Fixed-Length Extensions (Employee Directory)

```python
directory = PhoneTree(
    audio_file="menu/directory.mp3",
    extension_mode=True,
    extension_length=3,              # Exactly 3 digits required
    extension_terminator='#',
    extension_timeout=3.0,
    options={
        "101": PhoneTree("directory/alice.mp3", audio_handler=audio_handler),
        "102": PhoneTree("directory/bob.mp3", audio_handler=audio_handler),
        "103": PhoneTree("directory/charlie.mp3", audio_handler=audio_handler),
        "104": PhoneTree("directory/diana.mp3", audio_handler=audio_handler),
    }
)
```

### Variable-Length Extensions (Departments)

```python
departments = PhoneTree(
    audio_file="menu/departments.mp3",
    extension_mode=True,
    extension_terminator='#',        # User presses # to submit
    extension_timeout=3.0,            # Auto-submit after 3s of inactivity
    options={
        "10": PhoneTree("departments/sales.mp3", audio_handler=audio_handler),
        "20": PhoneTree("departments/support.mp3", audio_handler=audio_handler),
        "30": PhoneTree("departments/engineering.mp3", audio_handler=audio_handler),
    }
)
```

---

## User Experience Considerations

### Clear Instructions

Prompts should clearly indicate:
- How many digits to dial (for fixed-length)
- Whether to press # (for variable-length)
- What options are available

### Consistency

- Use the same voice across all prompts
- Maintain consistent volume levels
- Use similar phrasing patterns

### Error Handling

- `invalid_extension.mp3` should be polite and helpful
- Provide guidance on what went wrong if possible
- Always offer a way back to the main menu

---

## Testing Your Audio

Use the local test simulator to verify audio prompts:

```bash
python3 test_phone_tree.py
# Select mode 2 for Extension phone tree
# Follow prompts to test extension dialing
```

---

## Next Steps

1. Create/record the required audio files
2. Place them in the appropriate directories
3. Test with `test_phone_tree.py`
4. Deploy to the Raspberry Pi
5. Test with actual hardware

For questions or issues, refer to the main README or open an issue on GitHub.
