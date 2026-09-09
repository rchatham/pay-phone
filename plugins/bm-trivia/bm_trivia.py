"""Burning Man trivia questions and scoring helpers."""

from __future__ import annotations

import random
from dataclasses import dataclass

QUESTIONS_PER_ROUND = 5

TRIVIA_INTRO_TEXT = (
    "Welcome to Burning Man trivia. I will ask multiple choice questions about "
    "Black Rock City history and culture. Press the number of your answer. "
    "Your answer is submitted immediately. Press pound to end the game."
)


@dataclass(frozen=True)
class TriviaQuestion:
    """One multiple-choice trivia question."""

    prompt: str
    choices: tuple[str, ...]
    answer_index: int
    fact: str = ""

    def answer_number(self) -> int:
        """Return the 1-based DTMF digit of the correct choice."""
        return self.answer_index + 1

    def answer_text(self) -> str:
        """Return the spoken answer text."""
        return self.choices[self.answer_index]

    def is_correct(self, digits: str) -> bool:
        """Return true when entered DTMF digits match the answer number."""
        return digits.isdigit() and int(digits) == self.answer_number()

    def spoken_question(self, number: int) -> str:
        """Return this question as phone-friendly speech."""
        lines = [f"Question {number}. {self.prompt}"]
        for index, choice in enumerate(self.choices, start=1):
            lines.append(f"Press {index} for {choice}.")
        lines.append("Press your answer now.")
        return " ".join(lines)

    def spoken_answer(self, correct: bool) -> str:
        """Return the answer result as phone-friendly speech."""
        if correct:
            text = "Correct."
        else:
            text = f"Not quite. The answer was {self.answer_number()}, {self.answer_text()}."
        if self.fact:
            text += f" {self.fact}"
        return text


CURATED_QUESTIONS: tuple[TriviaQuestion, ...] = (
    TriviaQuestion(
        prompt="In what year was the first Burning Man?",
        choices=("1976", "1986", "1990", "1996"),
        answer_index=1,
        fact="Larry Harvey and Jerry James burned an eight foot wooden man on a San Francisco beach in 1986.",
    ),
    TriviaQuestion(
        prompt="Where was the first Burning Man held?",
        choices=("The Black Rock Desert", "Fly Ranch", "Baker Beach in San Francisco", "Golden Gate Park"),
        answer_index=2,
        fact="The event started on Baker Beach and moved to the Nevada desert in 1990.",
    ),
    TriviaQuestion(
        prompt="In what year did Burning Man move to the Black Rock Desert in Nevada?",
        choices=("1988", "1990", "1994", "1999"),
        answer_index=1,
    ),
    TriviaQuestion(
        prompt="What is the name of the temporary city built for Burning Man?",
        choices=("Black Rock City", "Playa City", "Dust Haven", "New Reno"),
        answer_index=0,
        fact="Black Rock City is rebuilt from scratch every year and disappears when the event ends.",
    ),
    TriviaQuestion(
        prompt="Which of these is one of the Ten Principles of Burning Man?",
        choices=("Constant Connectivity", "Competitive Spirit", "Cash Commerce", "Radical Self Reliance"),
        answer_index=3,
        fact="Larry Harvey wrote the Ten Principles in 2004. Leaving no trace is another one.",
    ),
    TriviaQuestion(
        prompt="On which night does the Temple traditionally burn?",
        choices=("Friday", "Saturday", "Sunday", "Monday"),
        answer_index=2,
        fact="The Man burns on Saturday night, and the quiet Temple burn closes the event on Sunday.",
    ),
    TriviaQuestion(
        prompt="What does the playa term MOOP stand for?",
        choices=("Matter Out Of Place", "Music On Open Playa", "Mind Over Ordinary People", "Maximum Output Of Participation"),
        answer_index=0,
        fact="Picking up MOOP keeps the leave no trace principle alive.",
    ),
    TriviaQuestion(
        prompt="In which two recent years was there no official Burning Man event in the desert?",
        choices=("2016 and 2017", "2018 and 2019", "2020 and 2021", "2022 and 2023"),
        answer_index=2,
    ),
    TriviaQuestion(
        prompt="Roughly how many people attended Burning Man in 2019?",
        choices=("Eight thousand", "Twenty five thousand", "Eighty thousand", "Two hundred thousand"),
        answer_index=2,
    ),
    TriviaQuestion(
        prompt="How are Black Rock City's radial streets named?",
        choices=("After clock positions", "After United States presidents", "After desert animals", "After famous artists"),
        answer_index=0,
    ),
    TriviaQuestion(
        prompt="What marks the edge of Black Rock City?",
        choices=("A river", "The trash fence", "A highway", "A row of art cars"),
        answer_index=1,
        fact="The perimeter trash fence catches wind blown MOOP.",
    ),
    TriviaQuestion(
        prompt="What is the Golden Spike?",
        choices=(
            "The award for the best mutant vehicle",
            "A sculpture burned before the Man",
            "The first stake placed when surveying the city",
            "The tallest point of the Temple",
        ),
        answer_index=2,
        fact="Driving the Golden Spike at the future site of the Man starts the survey of Black Rock City each year.",
    ),
)


class TriviaGame:
    """Build Burning Man trivia rounds from curated questions."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()

    def build_round(self, count: int = QUESTIONS_PER_ROUND) -> list[TriviaQuestion]:
        """Return a shuffled round of at most count questions."""
        pool = list(CURATED_QUESTIONS)
        self.rng.shuffle(pool)
        return pool[:count]


def score_summary(score: int, asked: int) -> str:
    """Return the spoken end-of-game score message."""
    if asked == 0:
        return "No trivia questions were answered. Returning to the BIOS switchboard."
    text = f"You answered {score} out of {asked} correctly."
    if score == asked:
        text += " A perfect score. You are a true Black Rock City historian."
    elif score >= asked / 2:
        text += " Well done, burner."
    else:
        text += " The playa still has lessons for you."
    return text + " Returning to the BIOS switchboard."
