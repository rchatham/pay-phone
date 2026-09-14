"""Hardware-independent regression tests for the Burning Man trivia plugin.

These tests pin two fixes:

1. The no-answer timeout must start *after* the question finishes playing so
   longer prompts are not cut off before the caller hears every choice.
2. The trivia loop must exit early when the call is cancelled (``running`` is
   cleared by the BIOS bootloader on hang-up) instead of continuing to play
   audio for a dead call.
"""

from __future__ import annotations

import threading
import time
from queue import Queue
from unittest.mock import Mock

from payphone.bios.system_manager import SystemManager


# The bm-trivia plugin directory uses a hyphen, so it cannot be imported with a
# normal ``from plugins.bm_trivia ...`` statement. Use the BIOS SystemManager to
# load it the same way the running phone does, then pull the constants and the
# system class off the loaded module.
_manager = SystemManager(scan_paths=["plugins"])
_manager.discover_systems()
_BM_TRIVIA_MODULE = _manager.load_system("bm-trivia").__module__
import importlib  # noqa: E402

_trivia_module = importlib.import_module(_BM_TRIVIA_MODULE)
BMTriviaSystem = _trivia_module.BMTriviaSystem
CURATED_QUESTIONS = _trivia_module.CURATED_QUESTIONS
QUESTIONS_PER_ROUND = _trivia_module.QUESTIONS_PER_ROUND
TRIVIA_INTRO_TEXT = _trivia_module.TRIVIA_INTRO_TEXT
TriviaGame = _trivia_module.TriviaGame
score_summary = _trivia_module.score_summary


class TimedAudioHandler:
    """Stub audio handler that reports playback for a fixed real duration."""

    def __init__(self, play_seconds: float = 0.0) -> None:
        self.play_seconds = play_seconds
        self.play_started_at: float | None = None
        self.played: list[tuple[str, bool]] = []
        self.stop_calls = 0

    def play_file(self, filename: str, blocking: bool = True) -> bool:
        self.played.append((filename, blocking))
        # Blocking plays are treated as already complete.
        self.play_started_at = None if blocking else time.time()
        return True

    def stop(self) -> None:
        self.stop_calls += 1
        self.play_started_at = None

    def is_playing(self) -> bool:
        if self.play_started_at is None:
            return False
        return time.time() - self.play_started_at < self.play_seconds


def build_trivia_system(
    audio_handler: TimedAudioHandler,
    input_queue: Queue | None = None,
    running: bool = True,
) -> BMTriviaSystem:
    """Build a BMTriviaSystem without touching hardware or pygame."""
    system = BMTriviaSystem.__new__(BMTriviaSystem)
    system.audio_handler = audio_handler
    system.hardware_handler = Mock(input_queue=input_queue or Queue())
    system.phone_on_hook = False
    system.running = running
    system.tts_available = False
    system.say = Mock()
    # Deterministic round: curated questions in their declared order.
    system.trivia = TriviaGame(rng=Mock())
    system.trivia.build_round = lambda count=QUESTIONS_PER_ROUND: list(
        CURATED_QUESTIONS[:count]
    )
    return system


def _valid_digits(question) -> set[str]:
    return {str(index) for index in range(1, len(question.choices) + 1)}


def test_answer_after_long_playback_is_accepted() -> None:
    """A valid answer pressed just after a long prompt should be accepted.

    With a 0.3s prompt and a 0.2s timeout, the old code started the timeout at
    playback start and would expire before the caller could answer. The fix
    starts the timeout after playback, so the late answer is accepted.
    """
    audio = TimedAudioHandler(play_seconds=0.3)
    queue: Queue = Queue()
    system = build_trivia_system(audio, input_queue=queue, running=True)
    question = CURATED_QUESTIONS[0]
    answer = str(question.answer_number())

    def press_later() -> None:
        time.sleep(0.35)  # after playback ends, within the post-playback window
        queue.put(answer)

    threading.Thread(target=press_later, daemon=True).start()

    digit = system._collect_answer("q.mp3", "text", _valid_digits(question), timeout=0.2)
    assert digit == answer


def test_no_answer_timeout_starts_after_playback() -> None:
    """The no-answer timeout must not elapse while the prompt is still playing."""
    audio = TimedAudioHandler(play_seconds=0.3)
    system = build_trivia_system(audio, running=True)
    question = CURATED_QUESTIONS[0]

    start = time.time()
    digit = system._collect_answer("q.mp3", "text", _valid_digits(question), timeout=0.2)
    elapsed = time.time() - start

    assert digit == ""
    # playback (0.3s) + timeout (0.2s) => at least ~0.5s. The old code returned
    # in ~0.2s because the timeout ran concurrently with playback.
    assert elapsed >= 0.45


def test_answer_interrupts_playback() -> None:
    """A valid DTMF digit during playback stops the prompt immediately."""
    audio = TimedAudioHandler(play_seconds=0.5)
    queue: Queue = Queue()
    system = build_trivia_system(audio, input_queue=queue, running=True)
    question = CURATED_QUESTIONS[0]
    answer = str(question.answer_number())

    def press_during_playback() -> None:
        time.sleep(0.15)
        queue.put(answer)

    threading.Thread(target=press_during_playback, daemon=True).start()

    start = time.time()
    digit = system._collect_answer("q.mp3", "text", _valid_digits(question), timeout=5.0)
    elapsed = time.time() - start

    assert digit == answer
    assert elapsed < 0.4  # interrupted well before the 0.5s prompt finished
    assert audio.stop_calls >= 1


def test_collect_answer_stops_on_cancellation() -> None:
    """The collection loop exits early when the call is cancelled mid-question."""
    audio = TimedAudioHandler(play_seconds=5.0)
    queue: Queue = Queue()
    system = build_trivia_system(audio, input_queue=queue, running=True)
    question = CURATED_QUESTIONS[0]

    def hang_up() -> None:
        time.sleep(0.2)
        system.running = False

    threading.Thread(target=hang_up, daemon=True).start()

    start = time.time()
    digit = system._collect_answer("q.mp3", "text", _valid_digits(question), timeout=20)
    elapsed = time.time() - start

    assert digit == ""
    assert elapsed < 1.0  # bailed out quickly instead of waiting 20s
    assert audio.stop_calls >= 1


def test_play_trivia_game_skips_score_when_cancelled() -> None:
    """A cancelled call plays no question or score audio after hang-up."""
    audio = TimedAudioHandler(play_seconds=0.0)
    system = build_trivia_system(audio, running=False)

    result = system._play_trivia_game()

    assert result is True
    played = [filename for filename, _ in audio.played]
    assert "bm-trivia/intro.mp3" in played
    assert not any(filename.startswith("bm-trivia/question_") for filename in played)
    assert not any(filename.startswith("bm-trivia/score_") for filename in played)


def test_play_trivia_game_scores_full_round() -> None:
    """A full round with all correct answers plays the perfect-score prompt."""
    audio = TimedAudioHandler(play_seconds=0.0)
    queue: Queue = Queue()
    system = build_trivia_system(audio, input_queue=queue, running=True)
    # Keep all answers queued; neutralise the per-question queue clear.
    system.clear_input_queue = lambda: 0  # type: ignore[method-assign]
    round_questions = list(CURATED_QUESTIONS[:QUESTIONS_PER_ROUND])
    for question in round_questions:
        queue.put(str(question.answer_number()))

    result = system._play_trivia_game()

    assert result is True
    played = [filename for filename, _ in audio.played]
    assert "bm-trivia/intro.mp3" in played
    for index in range(1, QUESTIONS_PER_ROUND + 1):
        assert f"bm-trivia/question_{index:02d}_round_{index}.mp3" in played
        assert f"bm-trivia/answer_{index:02d}_correct.mp3" in played
    assert "bm-trivia/score_5_of_5.mp3" in played


def test_play_trivia_game_records_wrong_answer_score() -> None:
    """A wrong answer produces the wrong-answer prompt and a non-perfect score."""
    audio = TimedAudioHandler(play_seconds=0.0)
    queue: Queue = Queue()
    system = build_trivia_system(audio, input_queue=queue, running=True)
    system.clear_input_queue = lambda: 0  # type: ignore[method-assign]
    round_questions = list(CURATED_QUESTIONS[:QUESTIONS_PER_ROUND])
    # First answer wrong, the rest correct.
    wrong_digit = next(
        str(d) for d in range(1, len(round_questions[0].choices) + 1)
        if str(d) != str(round_questions[0].answer_number())
    )
    queue.put(wrong_digit)
    for question in round_questions[1:]:
        queue.put(str(question.answer_number()))

    result = system._play_trivia_game()

    assert result is True
    played = [filename for filename, _ in audio.played]
    assert "bm-trivia/answer_01_wrong.mp3" in played
    assert "bm-trivia/score_4_of_5.mp3" in played
    assert "bm-trivia/score_5_of_5.mp3" not in played


def test_score_summary_covers_zero_asked() -> None:
    """The zero-question score message is the no-answer edge case."""
    assert "No trivia questions were answered" in score_summary(0, 0)