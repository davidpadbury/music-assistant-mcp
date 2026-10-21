"""Tests for the server entry point."""

import pytest

from music_assistant_mcp import server


def test_main_rejects_unknown_transport(monkeypatch):
    """An unsupported MCP_TRANSPORT value fails loudly instead of silently falling back."""
    monkeypatch.setenv("MCP_TRANSPORT", "bogus")
    with pytest.raises(ValueError, match="Unknown MCP_TRANSPORT"):
        server.main()


def test_http_bind_settings_defaults_and_overrides():
    """HTTP bind settings default to localhost:8844 and honor env overrides."""
    assert server.http_bind_settings({}) == ("127.0.0.1", 8844)
    assert server.http_bind_settings({"MCP_HOST": "0.0.0.0", "MCP_PORT": "9999"}) == (
        "0.0.0.0",
        9999,
    )


@pytest.mark.parametrize("port", ["abc", "-1", "70000"])
def test_http_bind_settings_rejects_invalid_ports(port):
    """Non-numeric or out-of-range MCP_PORT values fail loudly with a clear message."""
    with pytest.raises(ValueError, match="Invalid MCP_PORT"):
        server.http_bind_settings({"MCP_PORT": port})


def test_main_routes_streamable_http_with_bind_settings(monkeypatch):
    """MCP_TRANSPORT=streamable-http dispatches to run() with host/port."""
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(server.mcp, "run", fake_run)
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_PORT", "9000")

    server.main()

    assert calls == [
        ((), {"transport": "streamable-http", "host": "0.0.0.0", "port": 9000})
    ]


def test_main_routes_default_stdio(monkeypatch):
    """With MCP_TRANSPORT unset, main() dispatches to a bare run()."""
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(server.mcp, "run", fake_run)
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)

    server.main()

    assert calls == [((), {})]
