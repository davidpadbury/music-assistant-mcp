"""Tests for MCP tools registration."""

from mcp.server.fastmcp import FastMCP

from music_assistant_mcp.tools import music, playback, players, queue


async def mock_get_client():
    """Mock client getter that raises - used only for tool registration."""
    raise NotImplementedError("Mock client")


def test_player_tools_register():
    """Test that player tools register correctly."""
    mcp = FastMCP("test")
    players.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert "ma_list_players" in tool_names
    assert "ma_volume" in tool_names
    assert "ma_group" in tool_names


def test_playback_tools_register():
    """Test that playback tools register correctly."""
    mcp = FastMCP("test")
    playback.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert "ma_playback" in tool_names
    assert "ma_play_media" in tool_names


def test_queue_tools_register():
    """Test that queue tools register correctly."""
    mcp = FastMCP("test")
    queue.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert "ma_queue" in tool_names
    assert "ma_queue_item" in tool_names


def test_music_tools_register():
    """Test that music tools register correctly."""
    mcp = FastMCP("test")
    music.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert "ma_search" in tool_names
    assert "ma_browse" in tool_names


def test_all_tools_register():
    """Test that all 9 tools register without conflict."""
    mcp = FastMCP("test")
    players.register_tools(mcp, mock_get_client)
    playback.register_tools(mcp, mock_get_client)
    queue.register_tools(mcp, mock_get_client)
    music.register_tools(mcp, mock_get_client)

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    assert len(tool_names) == 9

    expected_tools = [
        "ma_list_players",
        "ma_volume",
        "ma_group",
        "ma_playback",
        "ma_play_media",
        "ma_queue",
        "ma_queue_item",
        "ma_search",
        "ma_browse",
    ]
    for tool in expected_tools:
        assert tool in tool_names, f"Missing tool: {tool}"
