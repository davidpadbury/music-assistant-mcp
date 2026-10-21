"""Shared result builders for mutation tools."""

from typing import Any

from mcp.types import CallToolResult, TextContent


def action_result(text: str, **fields: Any) -> CallToolResult:
    """Build a mutation-tool success: prose for chat, assertable structured fields."""
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content={"ok": True, **fields},
    )


def error_result(message: str) -> CallToolResult:
    """Build a validation-failure result: ok=False carries the reason."""
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        structured_content={"ok": False, "error": message},
    )
