"""Standalone Burning Man trivia phone system."""

from __future__ import annotations

import queue
import time

from payphone.core.phone_tree import PhoneTree
from payphone.core.system import PhoneSystemBase

from .bm_trivia import QUESTIONS_PER_ROUND, TRIVIA_INTRO_TEXT, TriviaGame, score_summary


class BMTriviaSystem(PhoneSystemBase):
    """Burning Man trivia game exposed as its own BIOS phone system."""

    @staticmethod
    def get_metadata() -> dict[str, str]:
        """Return BIOS discovery metadata."""
        return {
            "name": "Burning Man Trivia",
            "description": "Multiple-choice Burning Man history and culture trivia",
            "version": "1.0.0",
            "author": "Reid Chatham",
        }

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self.trivia = TriviaGame()

    def setup_phone_tree(self) -> PhoneTree:
        """Build the trivia entry point."""
        return PhoneTree(
            "",
            audio_handler=self.audio_handler,
            action=self._play_trivia_game,
            speech_text=TRIVIA_INTRO_TEXT,
            speech_handler=self,
            timeout=300,
        )

    def _play_trivia_game(self) -> bool:
        """Run one round of trivia over DTMF."""
        questions = self.trivia.build_round(QUESTIONS_PER_ROUND)
        if not questions:
            self.say("No trivia questions are available right now. Returning to the BIOS switchboard.", blocking=True)
            return True

        score = 0
        asked = 0
        for number, question in enumerate(questions, start=1):
            self.say(question.spoken_question(number), blocking=True)
            digits = self._collect_digits(timeout=20)
            if not digits:
                self.say("No answer was entered. Ending the trivia game.", blocking=True)
                break
            asked += 1
            correct = question.is_correct(digits)
            if correct:
                score += 1
            self.say(question.spoken_answer(correct), blocking=True)

        self.say(score_summary(score, asked), blocking=True)
        return True

    def _collect_digits(self, timeout: float = 10.0) -> str:
        """Collect DTMF digits until pound, star clear, or timeout."""
        input_queue = getattr(getattr(self, "hardware_handler", None), "input_queue", None)
        if input_queue is None:
            return ""

        deadline = time.time() + timeout
        digits: list[str] = []
        while time.time() < deadline:
            try:
                digit = input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if digit == "#":
                break
            if digit == "*":
                digits.clear()
                continue
            if digit in "0123456789":
                digits.append(digit)
        return "".join(digits)

    def stop_speech(self) -> None:
        """Speech interruption hook used by PhoneTree."""
        self.audio_handler.stop()

    def is_speaking(self) -> bool:
        """Return whether speech is currently active."""
        return False
