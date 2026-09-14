"""Standalone Burning Man trivia phone system."""

from __future__ import annotations

import queue
import time

from payphone.core.phone_tree import PhoneTree
from payphone.core.system import PhoneSystemBase

from .bm_trivia import CURATED_QUESTIONS, QUESTIONS_PER_ROUND, TRIVIA_INTRO_TEXT, TriviaGame, TriviaQuestion, score_summary


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
            timeout=300,
        )

    def _play_trivia_game(self) -> bool:
        """Run one round of trivia over DTMF."""
        self._play_audio("bm-trivia/intro.mp3", TRIVIA_INTRO_TEXT, blocking=True)
        if not self.running:
            return True

        questions = self.trivia.build_round(QUESTIONS_PER_ROUND)
        if not questions:
            self._play_audio(
                "bm-trivia/no_questions.mp3",
                "No trivia questions are available right now. Returning to the BIOS switchboard.",
                blocking=True,
            )
            return True

        score = 0
        asked = 0
        for number, question in enumerate(questions, start=1):
            if not self.running:
                break
            self.clear_input_queue()
            digits = self._ask_question(question, number, timeout=20)
            if not self.running:
                break
            if not digits:
                self._play_audio(
                    "bm-trivia/no_answer.mp3",
                    "No answer was entered. Ending the trivia game.",
                    blocking=True,
                )
                break
            asked += 1
            correct = question.is_correct(digits)
            if correct:
                score += 1
            self._play_answer(question, correct)

        if not self.running:
            return True
        self._play_audio(f"bm-trivia/score_{score}_of_{asked}.mp3", score_summary(score, asked), blocking=True)
        return True

    def _ask_question(self, question: TriviaQuestion, number: int, timeout: float) -> str:
        """Play a question and return the first answer digit immediately."""
        question_number = CURATED_QUESTIONS.index(question) + 1
        return self._collect_answer(
            f"bm-trivia/question_{question_number:02d}_round_{number}.mp3",
            question.spoken_question(number),
            valid_digits={str(index) for index in range(1, len(question.choices) + 1)},
            timeout=timeout,
        )

    def _play_answer(self, question: TriviaQuestion, correct: bool) -> None:
        """Play the generated answer result for a trivia question."""
        question_number = CURATED_QUESTIONS.index(question) + 1
        suffix = "correct" if correct else "wrong"
        self._play_audio(
            f"bm-trivia/answer_{question_number:02d}_{suffix}.mp3",
            question.spoken_answer(correct),
            blocking=True,
        )

    def _collect_answer(self, audio_file: str, fallback_text: str, valid_digits: set[str], timeout: float) -> str:
        """Collect the first valid answer digit.

        DTMF may arrive while the question is still playing and immediately
        interrupts playback. The no-answer timeout only starts after the
        question finishes playing, so longer questions are not cut off before
        the caller has heard every choice. The loop also exits early when the
        call is cancelled (``self.running`` is cleared by the BIOS bootloader
        on hang-up).
        """
        input_queue = getattr(getattr(self, "hardware_handler", None), "input_queue", None)
        if input_queue is None:
            self._play_audio(audio_file, fallback_text, blocking=True)
            return ""

        self._play_audio(audio_file, fallback_text, blocking=False)

        # Accept answers while the question plays; interrupt on first valid digit.
        while self._is_audio_playing() and self.running:
            try:
                digit = input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if digit in valid_digits:
                self.audio_handler.stop()
                return digit
            if digit == "#":
                self.audio_handler.stop()
                return ""
            if digit == "*":
                self.audio_handler.stop()
                continue

        if not self.running:
            self.audio_handler.stop()
            return ""

        # Question finished playing; wait for an answer with a timeout.
        deadline = time.time() + timeout
        while time.time() < deadline and self.running:
            try:
                digit = input_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if digit in valid_digits:
                return digit
            if digit == "#":
                return ""
            if digit == "*":
                continue
        return ""

    def _is_audio_playing(self) -> bool:
        """Return whether the question prompt is currently playing."""
        return bool(self.audio_handler.is_playing()) if self.audio_handler else False

    def _play_audio(self, audio_file: str, fallback_text: str, blocking: bool) -> None:
        """Play generated audio, falling back to live TTS when the file is missing."""
        if self.audio_handler.play_file(audio_file, blocking=blocking):
            return
        self.say(fallback_text, blocking=blocking)

    def stop_speech(self) -> None:
        """Speech interruption hook used by PhoneTree."""
        self.audio_handler.stop()

    def is_speaking(self) -> bool:
        """Return whether speech is currently active."""
        return False
