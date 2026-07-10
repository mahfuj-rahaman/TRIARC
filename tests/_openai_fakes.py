"""Shared fake OpenAI client for testing constrained-decoding clients without a network call."""

from __future__ import annotations


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, total_tokens: int) -> None:
        self.total_tokens = total_tokens


class _FakeResponse:
    def __init__(self, content: str, total_tokens: int = 42) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(total_tokens)


class _FakeCompletions:
    def __init__(self, contents: list[str], total_tokens: int = 42) -> None:
        self._contents = list(contents)
        self._total_tokens = total_tokens
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._contents[len(self.calls) - 1] if len(self._contents) > 1 else self._contents[0]
        return _FakeResponse(content, total_tokens=self._total_tokens)

    @property
    def last_kwargs(self) -> dict | None:
        return self.calls[-1] if self.calls else None


class _FakeChat:
    def __init__(self, contents: list[str], total_tokens: int = 42) -> None:
        self.completions = _FakeCompletions(contents, total_tokens=total_tokens)


class FakeOpenAI:
    """Stands in for `openai.OpenAI`; returns CONTENT (or successive CONTENTS) as the
    assistant message content on each `chat.completions.create` call."""

    def __init__(self, content: str | list[str], total_tokens: int = 42) -> None:
        contents = content if isinstance(content, list) else [content]
        self.chat = _FakeChat(contents, total_tokens=total_tokens)


def install_fake_openai(
    monkeypatch, module_path: str, content: str | list[str], *, total_tokens: int = 42
) -> FakeOpenAI:
    fake = FakeOpenAI(content, total_tokens=total_tokens)
    monkeypatch.setattr(f"{module_path}.OpenAI", lambda base_url, api_key: fake)
    return fake
