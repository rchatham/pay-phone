#!/usr/bin/env python3
"""Generate payphone prompt audio files.

By default this script generates all static prompt files plus BIOS menu audio for
currently discovered phone systems. Provider selection is automatic:
OpenAI TTS when OPENAI_API_KEY is set, otherwise gTTS when available, otherwise
macOS `say` + ffmpeg. Use --provider qwen for local Qwen3-TTS generation.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal, TypedDict


Voice = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
Provider = Literal["auto", "openai", "gtts", "say", "qwen"]
_QWEN_MODEL_CACHE = None
_QWEN_MODEL_CACHE_KEY: tuple[str, str, str] | None = None


class AudioPrompt(TypedDict, total=False):
    text: str
    voice: Voice
    skip: bool


AUDIO_FILES: dict[str, AudioPrompt] = {
    # Prompts
    "prompts/dial_tone.mp3": {
        "text": "[This would be a dial tone sound - skipping for now]",
        "skip": True,
    },
    "prompts/timeout.mp3": {
        "text": "Sorry, we didn't receive your selection. Returning to the main menu.",
        "voice": "alloy",
    },
    "prompts/invalid_option.mp3": {
        "text": "That's not a valid option. Please try again.",
        "voice": "alloy",
    },
    "prompts/invalid_extension.mp3": {
        "text": "I'm sorry, that extension is not valid. Please try again.",
        "voice": "alloy",
    },
    "prompts/no_systems.mp3": {
        "text": "No phone systems found. Please check configuration.",
        "voice": "alloy",
    },

    # Information Booth example menus
    "menu/main_menu.mp3": {
        "text": "Welcome to the payphone menu system. Press 1 for information services. Press 2 to hear a joke. Press 3 for music.",
        "voice": "nova",
    },
    "menu/info_menu.mp3": {
        "text": "Information menu. Press 1 for weather information. Press 2 for time information.",
        "voice": "nova",
    },
    "menu/weather_info.mp3": {
        "text": "The weather today is sunny with a high of 72 degrees. Perfect weather for using a payphone! Returning to main menu.",
        "voice": "shimmer",
    },
    "menu/time_info.mp3": {
        "text": "The current time is... well, check your phone! Just kidding, this is a demonstration. Returning to main menu.",
        "voice": "shimmer",
    },
    "menu/jokes.mp3": {
        "text": "Here's a joke: Why did the smartphone go to therapy? Because it had too many hang-ups! Get it? Hang-ups? Like a payphone? Returning to main menu.",
        "voice": "echo",
    },
    "menu/music.mp3": {
        "text": "La la la, this is where music would play! Imagine your favorite hold music here. Returning to main menu.",
        "voice": "fable",
    },

    # Extension mode demo prompts
    "menu/main_menu_ext.mp3": {
        "text": "Welcome to the company directory. Press 1 for the employee directory. Press 2 for departments. Press 3 for general information.",
        "voice": "nova",
    },
    "menu/directory.mp3": {
        "text": "Employee directory. Please dial the three-digit extension of the person you wish to reach. Extension 101 for Alice, 102 for Bob, 103 for Charlie, or 104 for Diana.",
        "voice": "nova",
    },
    "menu/departments.mp3": {
        "text": "Department directory. Dial 10 for Sales, 20 for Support, or 30 for Engineering. Press pound when finished.",
        "voice": "nova",
    },
    "menu/info.mp3": {
        "text": "Company information. Our office hours are Monday through Friday, 9 AM to 5 PM Pacific Time. For technical support, please press 2 from the main menu and dial extension 20. Returning to main menu.",
        "voice": "shimmer",
    },
    "directory/alice.mp3": {
        "text": "You have reached Alice Smith in Marketing. I'm currently away from my desk. Please leave a message after the tone, or press pound to return to the directory. Returning to main menu.",
        "voice": "shimmer",
    },
    "directory/bob.mp3": {
        "text": "You have reached Bob Johnson in Engineering. I'm not available right now. Please leave your name and number, and I'll get back to you as soon as possible. Returning to main menu.",
        "voice": "onyx",
    },
    "directory/charlie.mp3": {
        "text": "You have reached Charlie Davis in Sales. Thank you for calling! I'm either on another call or away from my desk. Please leave a detailed message and I'll return your call. Returning to main menu.",
        "voice": "echo",
    },
    "directory/diana.mp3": {
        "text": "You have reached Diana Martinez in Human Resources. I'm currently unavailable. If this is regarding employment verification, please press 0 to reach the main desk. Otherwise, please leave a message.",
        "voice": "nova",
    },
    "departments/sales.mp3": {
        "text": "You have reached the Sales department. Our sales team is available Monday through Friday, 9 AM to 6 PM. For immediate assistance, please call our main line. For all other inquiries, please leave a message. Returning to main menu.",
        "voice": "echo",
    },
    "departments/support.mp3": {
        "text": "You have reached Technical Support. For 24/7 support, please visit our website or use our chat system. For non-urgent matters, please leave a detailed message including your contact information and a description of your issue. Returning to main menu.",
        "voice": "onyx",
    },
    "departments/engineering.mp3": {
        "text": "You have reached the Engineering department. For technical inquiries, please email engineering at company dot com. For urgent production issues, please contact the on-call engineer through the main desk. Returning to main menu.",
        "voice": "onyx",
    },

    # Leave a Message plugin prompts
    "lam/intro.mp3": {
        "text": "Leave a message. First, listen to someone who came before you.",
        "voice": "nova",
    },
    "lam/menu.mp3": {
        "text": "Press one to leave a message for the next person. Press two to listen to past messages from the burn. Dial star, then a three digit message number, then pound to hear a specific message. Press zero to return to the system menu.",
        "voice": "nova",
    },
    "lam/no_messages.mp3": {
        "text": "No one has left a message yet. You can be the first.",
        "voice": "shimmer",
    },
    "lam/no_past_messages.mp3": {
        "text": "There are no past messages yet.",
        "voice": "shimmer",
    },
    "lam/browse_intro.mp3": {
        "text": "Playing all past messages in the order they were left. Press zero to stop.",
        "voice": "nova",
    },
    "lam/returning_to_menu.mp3": {
        "text": "Returning to the menu.",
        "voice": "alloy",
    },
    "lam/end_of_messages.mp3": {
        "text": "End of messages.",
        "voice": "alloy",
    },
    "lam/record_prompt.mp3": {
        "text": "Record your message after the beep.",
        "voice": "nova",
    },
    "lam/record_controls.mp3": {
        "text": "Press pound to save, star to re-record, or zero to cancel.",
        "voice": "nova",
    },
    "lam/recording_unavailable.mp3": {
        "text": "Sorry, recording is not available right now.",
        "voice": "alloy",
    },
    "lam/saved_as_message.mp3": {
        "text": "Thank you. Your message has been saved as message.",
        "voice": "shimmer",
    },
    "lam/time_up_saved_as_message.mp3": {
        "text": "Time is up. Your message has been saved as message.",
        "voice": "shimmer",
    },
    "lam/recording_again.mp3": {
        "text": "Recording again.",
        "voice": "nova",
    },
    "lam/recording_cancelled.mp3": {
        "text": "Recording cancelled.",
        "voice": "alloy",
    },
    "lam/recording_error.mp3": {
        "text": "Sorry, there was an error recording your message.",
        "voice": "alloy",
    },
    "lam/message_not_found.mp3": {
        "text": "Sorry, that message does not exist.",
        "voice": "alloy",
    },
    "lam/playing_message.mp3": {
        "text": "Playing message.",
        "voice": "nova",
    },
}


def generate_with_openai(text: str, output_path: Path, voice: Voice) -> None:
    from openai import OpenAI

    client = OpenAI()
    response = client.audio.speech.create(model="tts-1", voice=voice, input=text)
    response.stream_to_file(output_path)


def generate_with_gtts(text: str, output_path: Path) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="en", slow=False).save(str(output_path))


def _convert_to_mp3(input_path: Path, output_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to convert generated audio to MP3")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(output_path),
        ],
        check=True,
    )


def generate_with_say(text: str, output_path: Path) -> None:
    if not Path("/usr/bin/say").exists():
        raise RuntimeError("macOS say command is not available")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required when using the say provider")

    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        subprocess.run(["say", "-o", str(tmp_path), text], check=True)
        _convert_to_mp3(tmp_path, output_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def generate_with_qwen(
    text: str,
    output_path: Path,
    model: str,
    speaker: str,
    language_type: str,
    dtype_name: str,
    device_name: str,
) -> None:
    try:
        import soundfile as sf
        import torch
        from qwen_tts import Qwen3TTSModel
    except ImportError as exc:
        raise RuntimeError(
            "Local Qwen3-TTS dependencies are not installed. Install them in a dedicated environment with: "
            "python3 -m pip install -U qwen-tts soundfile torch"
        ) from exc

    tts_model = _load_qwen_model(Qwen3TTSModel, torch, model, dtype_name, device_name)
    wavs, sample_rate = tts_model.generate_custom_voice(
        text=text,
        language=language_type,
        speaker=speaker,
    )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        sf.write(tmp_path, wavs[0], sample_rate)
        if output_path.suffix.lower() == ".wav":
            shutil.copyfile(tmp_path, output_path)
        else:
            _convert_to_mp3(tmp_path, output_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _load_qwen_model(qwen_model_class, torch_module, model: str, dtype_name: str, device_name: str):
    global _QWEN_MODEL_CACHE, _QWEN_MODEL_CACHE_KEY

    cache_key = (model, dtype_name, device_name)
    if _QWEN_MODEL_CACHE is not None and _QWEN_MODEL_CACHE_KEY == cache_key:
        return _QWEN_MODEL_CACHE

    model_kwargs = {"device_map": None if device_name == "auto" else device_name}
    dtype = _torch_dtype(torch_module, dtype_name)
    if dtype is not None:
        model_kwargs["dtype"] = dtype

    print(f"  Loading local Qwen3-TTS model: {model}")
    _QWEN_MODEL_CACHE = qwen_model_class.from_pretrained(model, **model_kwargs)
    _QWEN_MODEL_CACHE_KEY = cache_key
    return _QWEN_MODEL_CACHE


def _torch_dtype(torch_module, name: str):
    if name == "auto":
        return None
    return {
        "float16": torch_module.float16,
        "bfloat16": torch_module.bfloat16,
        "float32": torch_module.float32,
    }[name]


def choose_provider(requested: Provider) -> Literal["openai", "gtts", "say", "qwen"]:
    if requested != "auto":
        return requested
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    try:
        import gtts  # noqa: F401
        return "gtts"
    except ImportError:
        return "say"


def generate_audio_file(
    filepath: Path,
    text: str,
    provider: Literal["openai", "gtts", "say", "qwen"],
    voice: Voice,
    qwen_model: str,
    qwen_speaker: str,
    qwen_language: str,
    qwen_dtype: str,
    qwen_device: str,
) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    print(f"Generating: {filepath}")

    if provider == "openai":
        generate_with_openai(text, filepath, voice)
    elif provider == "gtts":
        generate_with_gtts(text, filepath)
    elif provider == "qwen":
        generate_with_qwen(
            text,
            filepath,
            qwen_model,
            qwen_speaker,
            qwen_language,
            qwen_dtype,
            qwen_device,
        )
    else:
        generate_with_say(text, filepath)

    print(f"  ✓ Saved to {filepath}")


def _ordered_bios_systems(systems):
    priority = {system_id: index for index, system_id in enumerate(("TDTM", "LAM", "bm-trivia", "bm-info-line"))}
    return sorted(systems.items(), key=lambda item: (priority.get(item[0], len(priority)), item[1].name))


def discover_bios_prompts() -> dict[str, AudioPrompt]:
    from types import SimpleNamespace

    from payphone.bios.system_manager import SystemManager

    manager = SystemManager(scan_paths=["./phone_systems", "./plugins"])
    systems = manager.discover_systems()
    if "TDTM" not in systems and Path("plugins/TDTM").exists():
        systems["TDTM"] = SimpleNamespace(name="Talk Dirty To Me")
    ordered_systems = _ordered_bios_systems(systems)
    prompts: dict[str, AudioPrompt] = {}

    if ordered_systems:
        menu_parts = [
            "Welcome home. You have reached the Black Rock City payphone switchboard."
        ]
        for idx, (_, info) in enumerate(ordered_systems, start=1):
            menu_parts.append(f"Press {idx} for {info.name}.")
        menu_parts.append("Stay dusty, and leave no trace.")
        prompts["bios/main_menu.mp3"] = {"text": " ".join(menu_parts), "voice": "nova"}
    else:
        prompts["bios/main_menu.mp3"] = {
            "text": (
                "Welcome home. You have reached the Black Rock City payphone switchboard. "
                "No camps, art cars, or phone systems are on the line yet. Please check configuration."
            ),
            "voice": "nova",
        }

    for system_id, info in ordered_systems:
        prompts[f"bios/system_{system_id}.mp3"] = {
            "text": info.name,
            "voice": "shimmer",
        }

    return prompts


def discover_trivia_prompts() -> dict[str, AudioPrompt]:
    module_path = Path("plugins/bm-trivia/bm_trivia.py")
    if not module_path.exists():
        return {}

    spec = importlib.util.spec_from_file_location("bm_trivia_prompts", module_path)
    if spec is None or spec.loader is None:
        return {}

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    prompts: dict[str, AudioPrompt] = {
        "bm-trivia/intro.mp3": {"text": module.TRIVIA_INTRO_TEXT, "voice": "nova"},
        "bm-trivia/no_questions.mp3": {
            "text": "No trivia questions are available right now. Returning to the BIOS switchboard.",
            "voice": "alloy",
        },
        "bm-trivia/no_answer.mp3": {
            "text": "No answer was entered. Ending the trivia game.",
            "voice": "alloy",
        },
    }

    for index, question in enumerate(module.CURATED_QUESTIONS, start=1):
        for round_number in range(1, module.QUESTIONS_PER_ROUND + 1):
            prompts[f"bm-trivia/question_{index:02d}_round_{round_number}.mp3"] = {
                "text": question.spoken_question(round_number),
                "voice": "nova",
            }
        prompts[f"bm-trivia/answer_{index:02d}_correct.mp3"] = {
            "text": question.spoken_answer(True),
            "voice": "shimmer",
        }
        prompts[f"bm-trivia/answer_{index:02d}_wrong.mp3"] = {
            "text": question.spoken_answer(False),
            "voice": "alloy",
        }

    for asked in range(0, module.QUESTIONS_PER_ROUND + 1):
        for score in range(0, asked + 1):
            prompts[f"bm-trivia/score_{score}_of_{asked}.mp3"] = {
                "text": module.score_summary(score, asked),
                "voice": "shimmer",
            }

    return prompts


def build_prompt_set(include_bios: bool, include_trivia: bool) -> dict[str, AudioPrompt]:
    prompts = dict(AUDIO_FILES)
    if include_bios:
        prompts.update(discover_bios_prompts())
    if include_trivia:
        prompts.update(discover_trivia_prompts())
    return prompts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate payphone TTS audio prompts.")
    parser.add_argument("--audio-dir", default="audio_files", help="Base output directory")
    parser.add_argument(
        "--provider",
        choices=["auto", "openai", "gtts", "say", "qwen"],
        default="auto",
        help="TTS provider to use",
    )
    parser.add_argument(
        "--qwen-model",
        default=os.getenv("PAYPHONE_QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"),
        help="Local Hugging Face model ID for Qwen3-TTS",
    )
    parser.add_argument(
        "--qwen-speaker",
        default=os.getenv("PAYPHONE_QWEN_TTS_SPEAKER", "eric"),
        help="Built-in speaker name for Qwen3-TTS CustomVoice models",
    )
    parser.add_argument(
        "--qwen-voice",
        default=None,
        help="Alias for --qwen-speaker, kept for compatibility with earlier Qwen commands",
    )
    parser.add_argument(
        "--qwen-language",
        default=os.getenv("PAYPHONE_QWEN_TTS_LANGUAGE", "English"),
        help="Language label passed to Qwen3-TTS",
    )
    parser.add_argument(
        "--qwen-device",
        default=os.getenv("PAYPHONE_QWEN_TTS_DEVICE", "auto"),
        help="Qwen3-TTS device_map, for example auto, cpu, cuda:0, or mps",
    )
    parser.add_argument(
        "--qwen-dtype",
        default=os.getenv("PAYPHONE_QWEN_TTS_DTYPE", "auto"),
        choices=("auto", "float16", "bfloat16", "float32"),
        help="Torch dtype for Qwen3-TTS",
    )
    parser.add_argument(
        "--only-prefix",
        action="append",
        default=[],
        help="Only generate prompt paths with this relative prefix; may be passed more than once",
    )
    parser.add_argument("--no-bios", action="store_true", help="Skip dynamic BIOS menu/system prompts")
    parser.add_argument("--no-trivia", action="store_true", help="Skip Burning Man trivia prompts")
    parser.add_argument("--skip-existing", action="store_true", help="Do not regenerate audio files that already exist")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    provider = choose_provider(args.provider)
    qwen_speaker = args.qwen_voice or args.qwen_speaker
    audio_dir = Path(args.audio_dir)
    prompts = build_prompt_set(include_bios=not args.no_bios, include_trivia=not args.no_trivia)
    if args.only_prefix:
        prefixes = tuple(args.only_prefix)
        prompts = {
            relative_path: config
            for relative_path, config in prompts.items()
            if relative_path.startswith(prefixes)
        }

    print("=" * 60)
    print(f"Generating Payphone Audio Files with {provider}")
    print("=" * 60)

    generated = 0
    failures: list[tuple[str, Exception]] = []
    for relative_path, config in prompts.items():
        if config.get("skip"):
            print(f"Skipping: {relative_path} (sound effect)")
            continue

        output_path = audio_dir / relative_path
        if args.skip_existing and output_path.exists():
            print(f"Skipping: {relative_path} (already exists)")
            continue

        try:
            generate_audio_file(
                output_path,
                config["text"],
                provider,
                config.get("voice", "alloy"),
                args.qwen_model,
                qwen_speaker,
                args.qwen_language,
                args.qwen_dtype,
                args.qwen_device,
            )
            generated += 1
        except Exception as exc:
            failures.append((relative_path, exc))
            print(f"  ✗ Error generating {relative_path}: {exc}")

    print("=" * 60)
    print(f"Audio generation complete: {generated} files")
    if failures:
        print(f"Failures: {len(failures)}")
        for relative_path, exc in failures:
            print(f"  - {relative_path}: {exc}")
    print(f"Files saved to: {audio_dir.absolute()}")
    print("=" * 60)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
