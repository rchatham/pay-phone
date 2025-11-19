# Audio Files for Payphone Extension Mode

## Missing Audio Files

The following audio files are required for extension mode but are not yet generated:

### Required Files

**Prompts:**
- `prompts/invalid_extension.mp3` - Error message for invalid extensions

**Menus:**
- `menu/main_menu_ext.mp3` - Main menu for extension-based system
- `menu/directory.mp3` - Employee directory prompt
- `menu/departments.mp3` - Department directory prompt
- `menu/info.mp3` - General information message

**Directory (Employee Voicemails):**
- `directory/alice.mp3` - Alice Smith (Marketing)
- `directory/bob.mp3` - Bob Johnson (Engineering)
- `directory/charlie.mp3` - Charlie Davis (Sales)
- `directory/diana.mp3` - Diana Martinez (HR)

**Departments:**
- `departments/sales.mp3` - Sales department message
- `departments/support.mp3` - Technical support message
- `departments/engineering.mp3` - Engineering department message

## How to Generate Audio Files

### Option 1: Using OpenAI TTS (Recommended)

1. Get your OpenAI API key from https://platform.openai.com/api-keys
2. Set the environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
   Or add it to `.env.payphone`:
   ```bash
   OPENAI_API_KEY=your-api-key-here
   ```

3. Run the generation script:
   ```bash
   python3 generate_audio.py
   ```

This will generate all audio files with natural-sounding voices using OpenAI's TTS API.

### Option 2: Using Other TTS Services

You can use any of these alternatives:

**Google Cloud Text-to-Speech:**
```bash
# Install the client library
pip install google-cloud-texttospeech

# Follow Google Cloud TTS documentation
# https://cloud.google.com/text-to-speech/docs
```

**Amazon Polly:**
```bash
# Install AWS CLI and SDK
pip install boto3

# Configure AWS credentials
aws configure

# Use Polly TTS
# https://aws.amazon.com/polly/
```

**ElevenLabs:**
- Visit https://elevenlabs.io/
- Very realistic voices
- API available for automation

### Option 3: Record Your Own

1. Use a quiet environment
2. Record in WAV format (44.1kHz, 16-bit)
3. Convert to MP3:
   ```bash
   ffmpeg -i input.wav -codec:a libmp3lame -b:a 128k output.mp3
   ```

### Option 4: Use Existing System TTS

**macOS:**
```bash
say -v Samantha "Your message here" -o output.aiff
ffmpeg -i output.aiff output.mp3
```

**Linux:**
```bash
espeak "Your message here" --stdout | ffmpeg -i - output.mp3
```

## Audio Specifications

- **Format**: MP3
- **Sample Rate**: 44.1kHz (recommended)
- **Bit Rate**: 128kbps or higher
- **Channels**: Mono or Stereo
- **Duration**: 5-30 seconds per file

## Testing Without Audio Files

The system will log warnings if audio files are missing but will continue to function. You can test the phone tree logic without audio by watching the console logs.

## Quick Start

To generate all files quickly with OpenAI TTS:

```bash
# Export API key (get from 1Password or https://platform.openai.com)
export OPENAI_API_KEY="sk-..."

# Generate all audio files
python3 generate_audio.py

# Verify files were created
find audio_files -name "*.mp3" | wc -l
```

You should see 20+ MP3 files after generation.

## See Also

- `docs/EXTENSION_MODE_AUDIO_PROMPTS.md` - Detailed documentation
- `generate_audio.py` - Audio generation script with all prompts
- `test_phone_tree.py` - Test the phone tree locally
