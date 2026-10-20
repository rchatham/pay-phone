"""Canonical Information Booth: public services and capability-protected editing."""
from __future__ import annotations

import copy
import logging
import os
import queue
import time
import uuid
from pathlib import Path
from typing import Callable

from payphone.audio import recording
from payphone.core import PhoneSystemBase, PhoneTree

from .content import AdminCapability, SERVICES, safe_media_path
from .services import current_time_text, joke_text
from .state import state_for_directory

logger = logging.getLogger(__name__)
TIMEZONES = ("local", "UTC", "America/New_York", "America/Chicago", "America/Denver",
             "America/Los_Angeles", "Europe/London", "Europe/Paris", "Asia/Tokyo")


class BoothTree(PhoneTree):
    """A single iterative Booth session; no recursive menus or extra input thread."""
    def __init__(self, system: InformationBoothSystem, runner: Callable[[], None]) -> None:
        super().__init__("", audio_handler=system.audio_handler, speech_handler=system)
        self.system = system
        self.runner = runner

    def navigate(self, input_queue: queue.Queue, hook_status: Callable[[], bool],
                 main_menu: PhoneTree | None = None) -> None:
        if hook_status() and self.system.is_call_active():
            try:
                self.runner()
            finally:
                self.system.stop_speech()
                self.system.audio_handler.stop()


class InformationBoothSystem(PhoneSystemBase):
    """Configurable local information, current weather/time, jokes and music."""
    def __init__(self, config=None) -> None:
        super().__init__(config)
        state = state_for_directory()
        self.store = state.store
        self.content = self.store.reload()
        self.weather_service = state.weather

    @staticmethod
    def get_metadata() -> dict[str, str]:
        return {"name": "Information Booth", "description": "Local information, weather, time, jokes and music",
                "version": "1.0.0"}

    def setup_phone_tree(self) -> PhoneTree:
        self.content = self.store.reload()
        return BoothTree(self, self._public_menu)

    def setup_admin_tree(self, admin_session: AdminCapability) -> PhoneTree:
        admin_session.require_authorized()
        self.content = self.store.reload()
        return BoothTree(self, lambda: self._admin_menu(admin_session))

    def _active(self, admin: AdminCapability | None = None) -> bool:
        if not self.is_call_active():
            return False
        if admin is not None:
            admin.require_authorized()
        return True

    def _speak(self, text: str, admin: AdminCapability | None = None) -> None:
        if not self._active(admin):
            return
        if admin is None:
            self.speak(text)
            return
        # Blocking speech prevents expiry polling. Do not consume keypad input
        # here: unlike menus, diagnostics/previews leave confirmation keys queued.
        deadline = time.monotonic() + 120
        try:
            self.say(text, blocking=False)
            while self._active(admin) and self.is_speaking():
                if time.monotonic() >= deadline:
                    logger.warning("Booth speech exceeded playback limit")
                    break
                time.sleep(0.05)
        finally:
            self.stop_speech()

    def _key(self, timeout: float, admin: AdminCapability | None = None) -> str | None:
        deadline = time.monotonic() + timeout
        while self._active(admin) and time.monotonic() < deadline:
            try:
                key = self.hardware_handler.input_queue.get(timeout=min(0.05, max(0.001, deadline - time.monotonic())))
                if not self._active(admin):
                    return None
                return key
            except queue.Empty:
                continue
        return None

    def _prompt_part(self, text: str | None, audio: str | None,
                     admin: AdminCapability | None = None) -> str | None:
        if not self._active(admin):
            return None
        if audio:
            try:
                path = safe_media_path(self.store.media_root, audio)
                if not self._active(admin):
                    return None
                if not self.audio_handler.play_file(str(path), blocking=False):
                    raise RuntimeError("Audio playback failed")
            except PermissionError:
                raise
            except (ValueError, OSError, RuntimeError) as exc:
                logger.warning("Booth label audio unavailable: %s", exc)
                if text:
                    self.say(text, blocking=False)
        elif text:
            self.say(text, blocking=False)
        deadline = time.monotonic() + 120
        try:
            while self._active(admin) and (self.is_speaking() or self.audio_handler.is_playing()):
                if time.monotonic() > deadline:
                    logger.warning("Booth prompt exceeded playback limit")
                    break
                key = self._key(0.05, admin)
                if key is not None:
                    return key
        finally:
            self.stop_speech()
            self.audio_handler.stop()
        return None

    def _choose(self, prompt: str, allowed: str, admin: AdminCapability | None = None,
                labels: list[tuple[str, str, str | None]] | None = None) -> str | None:
        """Speak dynamic menus with recorded labels; keypad barge-in is supported."""
        key = self._prompt_part(prompt, None, admin)
        if key is None and labels:
            for slot, text, audio in labels:
                key = self._prompt_part(f"Press {slot} for", None, admin)
                if key is None:
                    key = self._prompt_part(text, audio, admin)
                if key is not None:
                    break
        deadline = time.monotonic() + 45
        while self._active(admin) and time.monotonic() < deadline:
            if key is None:
                key = self._key(min(0.1, max(0.001, deadline - time.monotonic())), admin)
            if key is None:
                continue
            if key in allowed:
                return key
            self._speak("Invalid choice.", admin)
            key = None
        return None

    def _play_audio(self, name: str, admin: AdminCapability | None = None) -> bool:
        if not self._active(admin):
            return False
        try:
            path = safe_media_path(self.store.media_root, name)
            if not self._active(admin):
                return False
            if not self.audio_handler.play_file(str(path), blocking=False):
                raise RuntimeError("Playback failed")
            deadline = time.monotonic() + 180
            while self._active(admin) and self.audio_handler.is_playing() and time.monotonic() < deadline:
                key = self._key(0.05, admin)
                if key in ("0", "#"):
                    break
            return self._active(admin)
        except PermissionError:
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            logger.warning("Booth audio unavailable: %s", exc)
            self._speak("Audio is unavailable. Ask the administrator to check the local audio files.", admin)
            return False
        finally:
            self.audio_handler.stop()

    def _public_menu(self) -> None:
        while self._active():
            services = self.content["services"]
            labels = [(category["slot"], category["label"], category["label_audio"])
                      for category in sorted(self.content["categories"], key=lambda item: item["slot"])]
            if services["weather"] or services["time"]:
                labels.insert(0, ("1", "weather and time", None))
            if services["jokes"]:
                labels.append(("2", "jokes", None))
            if services["music"]:
                labels.append(("3", "music", None))
            choice = self._choose("Welcome to the information booth. Press 0 to repeat the menu.",
                                  "0" + "".join(item[0] for item in labels), labels=labels)
            if choice is None:
                return
            if choice == "1":
                self._information_menu()
            elif choice == "2":
                self._speak(joke_text())
            elif choice == "3":
                if self.content["music"]:
                    self._play_audio(self.content["music"])
                else:
                    self._speak("No local music is selected.")
            elif choice != "0":
                category = next(item for item in self.content["categories"] if item["slot"] == choice)
                self._category_menu(category)

    def _information_menu(self) -> None:
        services = self.content["services"]
        labels = [(slot, label, None) for slot, name, label in
                  (("1", "weather", "weather"), ("2", "time", "the current time")) if services[name]]
        while self._active():
            choice = self._choose("Information. Press 0 to go back.", "0" + "".join(item[0] for item in labels), labels=labels)
            if choice in (None, "0"):
                return
            if choice == "1":
                report = self.weather_service.report(self.content["weather"], self.is_call_active)
                # Network completion is not permission to speak after cancellation.
                self._speak(report)
            else:
                self._speak(current_time_text(self.content["timezone"]))

    def _category_menu(self, category: dict) -> None:
        while self._active():
            labels = [(message["slot"], message["label"], message["label_audio"])
                      for message in sorted(category["messages"], key=lambda item: item["slot"])]
            choice = self._choose(f"{category['label']}. Press 0 to go back.",
                                  "0" + "".join(item[0] for item in labels), labels=labels)
            if choice in (None, "0"):
                return
            message = next(item for item in category["messages"] if item["slot"] == choice)
            if message["audio"]:
                self._play_audio(message["audio"])
            else:
                self._speak(message["text"])

    def _confirm(self, admin: AdminCapability, prompt: str) -> bool:
        return self._choose(prompt + " Press 1 to save, or 0 to discard.", "10", admin) == "1"

    def _save(self, candidate: dict, admin: AdminCapability) -> None:
        if not self._active(admin):
            raise PermissionError("Call ended")
        self.store.save(candidate, admin)
        self.content = copy.deepcopy(self.store.snapshot)

    def _admin_menu(self, admin: AdminCapability) -> None:
        try:
            while self._active(admin):
                if self.store.reload_error:
                    self._speak("Local configuration was invalid. Last valid content is in use. Saving will replace the invalid file.", admin)
                choice = self._choose("Information booth administration. Press 1 for categories and messages. "
                                      "2 for service switches. 3 for weather settings. 4 for timezone. "
                                      "5 for local music. 0 to exit.", "123450", admin)
                if choice in (None, "0"):
                    return
                try:
                    if choice == "1":
                        self._edit_category(admin)
                    elif choice == "2":
                        self._edit_services(admin)
                    elif choice == "3":
                        self._edit_weather(admin)
                    elif choice == "4":
                        self._edit_timezone(admin)
                    elif choice == "5":
                        self._edit_music(admin)
                except PermissionError:
                    raise
                except (OSError, ValueError, RuntimeError) as exc:
                    logger.error("Booth admin operation failed: %s", exc)
                    self._speak("The operation failed or save durability is uncertain. Check the administrator logs and local content before retrying.", admin)
        except PermissionError:
            self.stop_speech()
            self.audio_handler.stop()
            logger.info("Booth administration ended: authorization or call expired")

    def _edit_services(self, admin: AdminCapability) -> None:
        prompt = "Service switches. " + " ".join(
            f"Press {index} to {'disable' if self.content['services'][name] else 'enable'} {name}."
            for index, name in enumerate(SERVICES, 1)) + " Press 0 to go back."
        choice = self._choose(prompt, "12340", admin)
        if choice in (None, "0"):
            return
        name = SERVICES[int(choice) - 1]
        candidate = copy.deepcopy(self.content)
        candidate["services"][name] = not candidate["services"][name]
        if self._confirm(admin, f"{name} will be {'enabled' if candidate['services'][name] else 'disabled'}."):
            self._save(candidate, admin)

    def _coordinate(self, name: str, bound: int, admin: AdminCapability) -> float | None:
        sign = self._choose(f"{name}. Press 1 for positive or 2 for negative. 0 to cancel.", "120", admin)
        if sign in (None, "0"):
            return None
        self._speak(f"Enter {name} digits. Use star as the decimal point. Finish with pound. Maximum {bound} degrees.", admin)
        digits = ""
        deadline = time.monotonic() + 45
        while self._active(admin) and time.monotonic() < deadline:
            key = self._key(0.1, admin)
            if key == "#":
                try:
                    value = float(digits) * (-1 if sign == "2" else 1)
                except ValueError as exc:
                    raise ValueError("Coordinate needs digits") from exc
                if abs(value) > bound:
                    raise ValueError("Coordinate out of range")
                return value
            if key is not None:
                if key == "*":
                    if "." in digits:
                        raise ValueError("Only one decimal point is allowed")
                    digits += "."
                elif key in "0123456789":
                    digits += key
                if len(digits) > 9:
                    raise ValueError("Coordinate input is too long")
        return None

    def _edit_weather(self, admin: AdminCapability) -> None:
        latitude = self._coordinate("latitude", 90, admin)
        if latitude is None:
            return
        longitude = self._coordinate("longitude", 180, admin)
        if longitude is None:
            return
        unit = self._choose("Press 1 for Celsius, 2 for Fahrenheit, or 0 to cancel.", "120", admin)
        if unit in (None, "0"):
            return
        candidate = copy.deepcopy(self.content)
        candidate["weather"] = {"latitude": latitude, "longitude": longitude,
                                "units": "celsius" if unit == "1" else "fahrenheit"}
        if self._confirm(admin, f"Latitude {latitude}, longitude {longitude}, {candidate['weather']['units']}."):
            self._save(candidate, admin)

    def _edit_timezone(self, admin: AdminCapability) -> None:
        labels = [(str(index), zone.replace("_", " "), None) for index, zone in enumerate(TIMEZONES, 1)]
        choice = self._choose("Timezone. Press 0 to cancel.", "0123456789", admin, labels)
        if choice in (None, "0"):
            return
        candidate = copy.deepcopy(self.content)
        candidate["timezone"] = TIMEZONES[int(choice) - 1]
        if self._confirm(admin, current_time_text(candidate["timezone"])):
            self._save(candidate, admin)

    def _edit_music(self, admin: AdminCapability) -> None:
        available = []
        if self.store.media_root.exists():
            for path in sorted(self.store.media_root.glob("*.wav")):
                # Recordings are private content, not an implicit music library.
                if path.name.startswith(("pending-", "recording-")):
                    continue
                try:
                    safe_media_path(self.store.media_root, path.name)
                except (ValueError, OSError):
                    continue
                available.append(path.name)
                if len(available) == 9:
                    break
        if not available:
            self._speak("No local music is available. Run the original sample generation script or add WAV files to the booth audio directory.", admin)
            return
        labels = [(str(index), name.removesuffix(".wav").replace("_", " "), None)
                  for index, name in enumerate(available, 1)]
        choice = self._choose("Local music. Press 0 to cancel.", "0" + "".join(item[0] for item in labels), admin, labels)
        if choice in (None, "0"):
            return
        name = available[int(choice) - 1]
        if not self._play_audio(name, admin):
            return
        if self._confirm(admin, f"Select {name}?"):
            candidate = copy.deepcopy(self.content)
            candidate["music"] = name
            self._save(candidate, admin)

    def _edit_category(self, admin: AdminCapability) -> None:
        slot = self._choose("Enter a category slot, 4 through 9. Empty slots create a new category. Press 0 to cancel.", "0456789", admin)
        if slot in (None, "0"):
            return
        category = next((item for item in self.content["categories"] if item["slot"] == slot), None)
        if category is None:
            candidate = copy.deepcopy(self.content)
            category = {"slot": slot, "label": f"Category {slot}", "label_audio": None, "messages": []}
            candidate["categories"].append(category)
            self._record_publish(candidate, category, "label_audio", admin)
            return
        choice = self._choose(f"Category {slot}, {category['label']}. Press 1 to record its label. "
                              "2 to edit messages. 3 to delete the category. 4 to move its slot. 0 to cancel.", "01234", admin)
        candidate = copy.deepcopy(self.content)
        target = next(item for item in candidate["categories"] if item["slot"] == slot)
        if choice == "1":
            self._record_publish(candidate, target, "label_audio", admin)
        elif choice == "2":
            self._edit_message(slot, admin)
        elif choice == "3" and self._confirm(admin, f"Delete category {slot} and all its message references?"):
            candidate["categories"].remove(target)
            self._save(candidate, admin)
        elif choice == "4":
            new_slot = self._choose("Enter an unused category slot, 4 through 9, or 0 to cancel.", "0456789", admin)
            if new_slot not in (None, "0"):
                target["slot"] = new_slot
                if self._confirm(admin, f"Move category to {new_slot}?"):
                    self._save(candidate, admin)

    def _edit_message(self, category_slot: str, admin: AdminCapability) -> None:
        slot = self._choose("Enter a message slot, 1 through 9. Empty slots create a recorded message. 0 to cancel.", "0123456789", admin)
        if slot in (None, "0"):
            return
        candidate = copy.deepcopy(self.content)
        category = next(item for item in candidate["categories"] if item["slot"] == category_slot)
        message = next((item for item in category["messages"] if item["slot"] == slot), None)
        if message is None:
            message = {"slot": slot, "label": f"Message {slot}", "label_audio": None, "text": "", "audio": None}
            category["messages"].append(message)
            self._record_publish(candidate, message, "audio", admin)
            return
        choice = self._choose(f"Message {slot}, {message['label']}. Press 1 to record content, "
                              "2 to record its label, 3 to preview, 4 to delete, 5 to move its slot. 0 to cancel.", "012345", admin)
        if choice in ("1", "2"):
            self._record_publish(candidate, message, "audio" if choice == "1" else "label_audio", admin)
        elif choice == "3":
            if message["audio"]:
                self._play_audio(message["audio"], admin)
            else:
                self._speak(message["text"], admin)
        elif choice == "4" and self._confirm(admin, f"Delete message {slot}?"):
            category["messages"].remove(message)
            self._save(candidate, admin)
        elif choice == "5":
            new_slot = self._choose("Enter an unused message slot, 1 through 9, or 0 to cancel.", "0123456789", admin)
            if new_slot not in (None, "0"):
                message["slot"] = new_slot
                if self._confirm(admin, f"Move message to {new_slot}?"):
                    self._save(candidate, admin)

    def _record_publish(self, candidate: dict, target: dict, field: str, admin: AdminCapability) -> None:
        """Stage, preview, explicitly confirm, publish unique WAV, then publish JSON."""
        if not self.config.ENABLE_RECORDING:
            self._speak("Recording is disabled. Enable recording in deployment settings and configure an input device.", admin)
            return
        if not self._active(admin):
            return
        if recording.is_recording:
            raise RuntimeError("Another recorder is already active")
        recording.init(preferred_device=self.config.RECORDING_DEVICE,
                       preferred_samplerate=self.config.RECORDING_SAMPLE_RATE,
                       preferred_channels=self.config.RECORDING_CHANNELS)
        root = self.store.media_root
        # Validate the root before creating unpublished media; never follow symlinks.
        token = uuid.uuid4().hex
        pending = safe_media_path(root, f"pending-{token}.wav", must_exist=False)
        published = safe_media_path(root, f"recording-{token}.wav", must_exist=False)
        admin.require_authorized()
        self.store.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        admin.require_authorized()
        root.mkdir(mode=0o700, exist_ok=True)
        started = False
        committed = False
        save_attempted = False
        pending_created = False
        published_created = False
        try:
            admin.require_authorized()
            pending.touch(mode=0o600, exist_ok=False)
            pending_created = True
            self._speak("Recording starts now. Press pound to finish, or star or 0 to cancel.", admin)
            if not self._active(admin):
                return
            admin.require_authorized()
            started = True  # Cleanup also covers partially failed backend startup.
            maximum = min(120, max(1, int(getattr(self.config, "LAM_MAX_RECORD_SECONDS", 60))))
            # Own the monotonic limit here: never stop a stream from its audio callback.
            recording.start_recording(pending, timeout=0)
            deadline = time.monotonic() + maximum
            finished = False
            while self._active(admin) and time.monotonic() < deadline:
                key = self._key(0.05, admin)
                if key in ("0", "*"):
                    return
                if key == "#":
                    finished = True
                    break
            if not self._active(admin):
                return
            if not finished:
                self._speak("Recording limit reached.", admin)
            recording.finish_recording()
            started = False
            safe_media_path(root, pending.name)
            if not self._play_audio(pending.name, admin):
                return
            if not self._confirm(admin, "Preview complete. Publish this recording?"):
                return
            # fsync audio before exposing a JSON reference; never overwrite an old recording.
            with pending.open("rb") as audio:
                os.fsync(audio.fileno())
            if not self._active(admin):
                return
            admin.require_authorized()
            # Hard-link publication is exclusive: even a UUID collision cannot
            # overwrite another recording. Both files are on the same filesystem.
            admin.protected_commit(lambda: os.link(pending, published))
            published_created = True
            pending.unlink()
            directory_fd = os.open(root, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            target[field] = published.name
            save_attempted = True
            self._save(candidate, admin)  # Stages JSON, then guards the final replacement.
            committed = True
            self._speak("Recording saved.", admin)
        finally:
            try:
                if started:
                    recording.cancel_recording()
            finally:
                # Only unpublished unique files are removed; published old recordings remain
                # available to previous snapshots/local editors. No destructive garbage collection.
                if pending_created and pending.exists():
                    pending.unlink()
                if (published_created and not committed and published.exists()
                        and (not save_attempted or not self.store.references_audio(published.name))):
                    published.unlink()
