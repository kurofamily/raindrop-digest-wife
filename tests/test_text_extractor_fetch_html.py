from __future__ import annotations

import httpx
import pytest

from raindrop_digest.text_extractor import ExtractionError, fetch_html


def test_fetch_html_retries_with_alternate_user_agent_on_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HTTP_USER_AGENT", raising=False)

    seen_user_agents: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agents.append(request.headers.get("User-Agent", ""))
        if len(seen_user_agents) == 1:
            return httpx.Response(403, request=request, text="blocked")
        return httpx.Response(200, request=request, text="<html>ok</html>")

    transport = httpx.MockTransport(handler)
    html_text = fetch_html("https://example.com/article", transport=transport)
    assert html_text == "<html>ok</html>"
    assert len(seen_user_agents) == 2
    assert seen_user_agents[0] != seen_user_agents[1]


def test_fetch_html_uses_env_user_agent_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_USER_AGENT", "MyCustomUA/1.0")

    seen_user_agents: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_user_agents.append(request.headers.get("User-Agent", ""))
        return httpx.Response(200, request=request, text="<html>ok</html>")

    transport = httpx.MockTransport(handler)
    fetch_html("https://example.com/article", transport=transport)
    assert seen_user_agents[0] == "MyCustomUA/1.0"


def test_fetch_html_raises_extraction_error_with_hint_on_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HTTP_USER_AGENT", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request, text="blocked")

    transport = httpx.MockTransport(handler)
    with pytest.raises(ExtractionError) as excinfo:
        fetch_html("https://example.com/article", transport=transport)

    # 最終的に403が続いた場合、運用時に原因切り分けしやすいようにヒントを含める。
    assert "403" in str(excinfo.value)
    assert "HTTP_USER_AGENT" in str(excinfo.value)


def test_fetch_html_wraps_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HTTP_USER_AGENT", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    transport = httpx.MockTransport(handler)
    with pytest.raises(ExtractionError) as excinfo:
        fetch_html("https://example.com/article", transport=transport)

    assert "HTTP request failed" in str(excinfo.value)
