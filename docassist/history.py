"""Remembering the conversation, so follow up questions make sense.

If you ask "How much is the deposit?" and then "When is it paid back?",
the second question on its own doesn't say what "it" is. The Conversation
keeps the last few turns so that:

- the AI model sees them and knows "it" means the deposit, and
- a short follow up is searched together with the question before it.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .answers import Answer
from .exceptions import ValidationError
from .llm import Message
from .text import tokens

# A question with fewer real words than this is treated as a follow up.
FOLLOW_UP_WORDS = 3


@dataclass(frozen=True)
class Turn:
    question: str
    answer: Answer


class Conversation:
    """The last max_turns questions and answers, oldest first."""

    def __init__(self, max_turns: int = 5) -> None:
        if max_turns < 1:
            raise ValidationError("max_turns must be at least 1.")
        # A deque with maxlen drops the oldest turn by itself when it's full.
        self._turns: deque[Turn] = deque(maxlen=max_turns)

    def __len__(self) -> int:
        return len(self._turns)

    @property
    def turns(self) -> list[Turn]:
        return list(self._turns)

    def add(self, answer: Answer) -> None:
        self._turns.append(Turn(answer.question, answer))

    def clear(self) -> None:
        self._turns.clear()

    def messages(self) -> list[Message]:
        """The turns as user and assistant messages, for the AI model."""
        out = []
        for turn in self._turns:
            out += [Message("user", turn.question), Message("assistant", turn.answer.text)]
        return out

    def search_query(self, question: str) -> str:
        """What to search for. Short follow ups borrow the words of the question before."""
        if self._turns and len(tokens(question)) < FOLLOW_UP_WORDS:
            return f"{self._turns[-1].question} {question}"
        return question
