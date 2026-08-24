"""Compatibility wrapper for the core PhoneTree implementation."""

from typing import Optional

from payphone.audio.handler import AudioHandler
from payphone.core.phone_tree import PhoneTree as CorePhoneTree


class PhoneTree(CorePhoneTree):
    """Deprecated import path for :class:`payphone.core.phone_tree.PhoneTree`."""

    def __init__(self, *args, audio_handler: Optional[AudioHandler] = None, **kwargs):
        super().__init__(*args, audio_handler=audio_handler if audio_handler is not None else AudioHandler(), **kwargs)


__all__ = ["PhoneTree", "AudioHandler"]
