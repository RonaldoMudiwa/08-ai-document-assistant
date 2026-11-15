import io
import json
import urllib.error

import pytest

from docassist import (
    API_URL,
    DEFAULT_MODEL,
    AnthropicProvider,
    FakeProvider,
    LLMProvider,
    Message,
    ProviderError,
    ValidationError,
)
from docassist import llm


class RecordingPost:
    """Stands in for the internet. Remembers the request and returns a set reply."""

    def __init__(self, reply):
        self.reply = reply
        self.requests = []

    def __call__(self, url, headers, body):
        self.requests.append((url, dict(headers), body))
        return self.reply


def text_reply(*texts):
    return {"content": [{"type": "text", "text": t} for t in texts]}


class TestMessage:
    def test_good_message(self):
        assert Message("user", "Hi").role == "user"

    @pytest.mark.parametrize("role,content", [("system", "Hi"), ("user", "  ")])
    def test_bad_message(self, role, content):
        with pytest.raises(ValidationError):
            Message(role, content)


class TestFakeProvider:
    def test_replies_in_order_and_records_calls(self):
        fake = FakeProvider("one", "two")
        assert isinstance(fake, LLMProvider)
        assert fake.complete("sys", [Message("user", "a")]) == "one"
        assert fake.complete("sys", [Message("user", "b")]) == "two"
        assert fake.calls[1] == ("sys", [Message("user", "b")])

    def test_runs_out(self):
        with pytest.raises(ProviderError, match="run out"):
            FakeProvider().complete("sys", [Message("user", "a")])


class TestAnthropicProvider:
    def test_sends_the_right_request(self):
        post = RecordingPost(text_reply("Hello", " there"))
        provider = AnthropicProvider("sk-test", max_tokens=50, post=post)
        assert provider.complete("Be kind.", [Message("user", "Hi")]) == "Hello there"
        url, headers, body = post.requests[0]
        assert url == API_URL
        assert headers["x-api-key"] == "sk-test"
        assert headers["anthropic-version"] == "2023-06-01"
        assert body == {"model": DEFAULT_MODEL, "max_tokens": 50, "system": "Be kind.",
                        "messages": [{"role": "user", "content": "Hi"}]}

    def test_ignores_blocks_that_are_not_text(self):
        reply = {"content": [{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "Yes"}]}
        assert AnthropicProvider("k", post=RecordingPost(reply)).complete("s", [Message("user", "q")]) == "Yes"

    @pytest.mark.parametrize("reply", [{}, {"content": "oops"}, {"content": [{"type": "text"}]}])
    def test_odd_reply_shape(self, reply):
        with pytest.raises(ProviderError, match="shape"):
            AnthropicProvider("k", post=RecordingPost(reply)).complete("s", [Message("user", "q")])

    def test_empty_reply(self):
        with pytest.raises(ProviderError, match="empty"):
            AnthropicProvider("k", post=RecordingPost(text_reply("  "))).complete(
                "s", [Message("user", "q")])

    def test_key_is_never_shown(self):
        provider = AnthropicProvider("sk-secret-123")
        assert "sk-secret" not in repr(provider)
        assert "sk-secret" not in str(provider)

    def test_needs_a_key(self):
        with pytest.raises(ProviderError):
            AnthropicProvider("  ")

    def test_bad_max_tokens(self):
        with pytest.raises(ValidationError):
            AnthropicProvider("k", max_tokens=0)

    def test_from_env(self):
        provider = AnthropicProvider.from_env({"ANTHROPIC_API_KEY": "k", "DOCASSIST_MODEL": "m"})
        assert provider.model == "m"

    def test_from_env_default_model(self):
        assert AnthropicProvider.from_env({"ANTHROPIC_API_KEY": "k"}).model == DEFAULT_MODEL

    def test_from_env_reads_the_real_environment(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.delenv("DOCASSIST_MODEL", raising=False)
        assert AnthropicProvider.from_env().model == DEFAULT_MODEL

    def test_from_env_without_a_key(self):
        with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
            AnthropicProvider.from_env({})


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestPostJson:
    def test_sends_json_and_reads_json(self, monkeypatch):
        seen = {}

        def fake_urlopen(request, timeout):
            seen["body"] = json.loads(request.data)
            seen["method"] = request.get_method()
            return FakeResponse(b'{"ok": true}')

        monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
        assert llm.post_json("https://x.test", {"a": "b"}, {"q": 1}) == {"ok": True}
        assert seen == {"body": {"q": 1}, "method": "POST"}

    def http_error(self, code, body):
        return urllib.error.HTTPError("https://x.test", code, "Bad", {}, io.BytesIO(body))

    @pytest.mark.parametrize("body,expected", [
        (b'{"error": {"message": "invalid x-api-key"}}', "invalid x-api-key"),
        (b"not json", "Bad"),
    ])
    def test_http_error(self, monkeypatch, body, expected):
        def fail(request, timeout):
            raise self.http_error(401, body)

        monkeypatch.setattr(llm.urllib.request, "urlopen", fail)
        with pytest.raises(ProviderError, match=f"said no \\(401\\): {expected}"):
            llm.post_json("https://x.test", {}, {})

    def test_cannot_connect(self, monkeypatch):
        def fail(request, timeout):
            raise urllib.error.URLError("no internet")

        monkeypatch.setattr(llm.urllib.request, "urlopen", fail)
        with pytest.raises(ProviderError, match="Couldn't reach"):
            llm.post_json("https://x.test", {}, {})

    def test_not_json(self, monkeypatch):
        monkeypatch.setattr(llm.urllib.request, "urlopen",
                            lambda request, timeout: FakeResponse(b"<html>"))
        with pytest.raises(ProviderError, match="isn't JSON"):
            llm.post_json("https://x.test", {}, {})
