"""Talking to a large language model (LLM), like Claude.

The rest of the program only knows about the LLMProvider base class. That
means the tests can use FakeProvider, which never goes online and costs
nothing, and the real AnthropicProvider is only used when you have a key.

The API key is read from the ANTHROPIC_API_KEY environment variable. It is
never written in the code, saved to a file, or printed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .exceptions import ProviderError, ValidationError

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"

# Sends a JSON body to a URL and returns the JSON reply. Swappable for tests.
PostFunction = Callable[[str, Mapping[str, str], dict], dict]


@dataclass(frozen=True)
class Message:
    """One turn in a conversation: who said it and what they said."""

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValidationError(f"role must be 'user' or 'assistant', not {self.role!r}.")
        if not self.content.strip():
            raise ValidationError("A message can't be empty.")


class LLMProvider(ABC):
    """Something that can read a conversation and write the next reply."""

    @abstractmethod
    def complete(self, system: str, messages: Sequence[Message]) -> str:
        """Return the model's reply to the last message. system holds the instructions."""


class FakeProvider(LLMProvider):
    """A pretend model for tests. Gives back the replies it was handed, in order.

    It also keeps every request, so a test can check what was sent.
    """

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, list[Message]]] = []

    def complete(self, system: str, messages: Sequence[Message]) -> str:
        self.calls.append((system, list(messages)))
        if not self._replies:
            raise ProviderError("The fake provider has run out of replies.")
        return self._replies.pop(0)


def post_json(url: str, headers: Mapping[str, str], body: dict, timeout: float = 60) -> dict:
    """Send a POST request with a JSON body and read the JSON reply."""
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ProviderError(f"The AI service said no ({error.code}): {_error_text(error)}") from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise ProviderError(f"Couldn't reach the AI service: {error}") from None
    except json.JSONDecodeError:
        raise ProviderError("The AI service sent back something that isn't JSON.") from None


def _error_text(error: urllib.error.HTTPError) -> str:
    """Pull the message out of an error reply, if there is one."""
    try:
        return json.loads(error.read().decode("utf-8"))["error"]["message"]
    except Exception:  # any problem reading it just means we have no details
        return error.reason or "no details"


class AnthropicProvider(LLMProvider):
    """Uses Claude through Anthropic's Messages API."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, max_tokens: int = 800,
                 post: PostFunction | None = None) -> None:
        if not api_key.strip():
            raise ProviderError("An API key is needed to use the AI model.")
        if max_tokens < 1:
            raise ValidationError("max_tokens must be at least 1.")
        self._api_key = api_key.strip()
        self.model = model
        self.max_tokens = max_tokens
        self._post = post or post_json

    def __repr__(self) -> str:
        # Never show the key, even by accident in an error message or a log.
        return f"AnthropicProvider(model={self.model!r})"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, **options) -> AnthropicProvider:
        """Build one from ANTHROPIC_API_KEY, and DOCASSIST_MODEL if it's set."""
        env = os.environ if env is None else env
        key = env.get("ANTHROPIC_API_KEY", "")
        if not key.strip():
            raise ProviderError("Set the ANTHROPIC_API_KEY environment variable to use the AI "
                                "model, or leave out --ai to answer offline.")
        if env.get("DOCASSIST_MODEL"):
            options.setdefault("model", env["DOCASSIST_MODEL"])
        return cls(key, **options)

    def complete(self, system: str, messages: Sequence[Message]) -> str:
        headers = {"x-api-key": self._api_key, "anthropic-version": API_VERSION,
                   "content-type": "application/json"}
        body = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                "messages": [{"role": m.role, "content": m.content} for m in messages]}
        reply = self._post(API_URL, headers, body)
        try:
            text = "".join(block["text"] for block in reply["content"] if block["type"] == "text")
        except (KeyError, TypeError):
            raise ProviderError("The AI service's reply wasn't in the expected shape.") from None
        if not text.strip():
            raise ProviderError("The AI service sent back an empty reply.")
        return text.strip()
