"""Integration tests for music discovery tools."""

import pytest
from music_assistant_client import MusicAssistantClient
from music_assistant_models.enums import MediaType


class TestSearch:
    """Tests for ma_search functionality."""

    async def test_search_returns_results(self, client: MusicAssistantClient):
        """Search returns results without error."""
        results = await client.music.search(
            search_query="test",
            media_types=MediaType.ALL,
            limit=5,
        )
        # Should return a SearchResults object without raising
        assert results is not None

    async def test_search_tracks(self, client: MusicAssistantClient):
        """Search for tracks returns track results."""
        results = await client.music.search(
            search_query="love",  # Common word in song titles
            media_types=[MediaType.TRACK],
            limit=5,
        )
        # Tracks may or may not be found depending on library
        # The test passes if no exception is raised
        if results.tracks:
            track = results.tracks[0]
            assert hasattr(track, "name")
            assert hasattr(track, "uri")

    async def test_search_artists(self, client: MusicAssistantClient):
        """Search for artists returns artist results."""
        results = await client.music.search(
            search_query="the",  # Common word in artist names
            media_types=[MediaType.ARTIST],
            limit=5,
        )
        if results.artists:
            artist = results.artists[0]
            assert hasattr(artist, "name")
            assert hasattr(artist, "uri")

    async def test_search_with_limit(self, client: MusicAssistantClient):
        """Search respects limit parameter."""
        results = await client.music.search(
            search_query="a",  # Very common letter
            media_types=MediaType.ALL,
            limit=3,
        )
        # Check that no category exceeds the limit
        if results.tracks:
            assert len(results.tracks) <= 3
        if results.artists:
            assert len(results.artists) <= 3
        if results.albums:
            assert len(results.albums) <= 3


class TestBrowse:
    """Tests for ma_browse functionality."""

    async def test_browse_root(self, client: MusicAssistantClient):
        """Browsing root level returns providers."""
        items = await client.music.browse(None)
        assert items is not None
        assert len(items) > 0, "Expected at least one provider"

    async def test_browse_items_have_uri(self, client: MusicAssistantClient):
        """Browse items have URIs for navigation."""
        items = await client.music.browse(None)
        for item in items:
            assert hasattr(item, "uri"), "Browse item missing uri"
            assert hasattr(item, "name"), "Browse item missing name"

    async def test_browse_provider_path(self, client: MusicAssistantClient):
        """Can browse into a provider path."""
        # Get root items first
        root_items = await client.music.browse(None)
        if not root_items:
            pytest.skip("No browse items available")

        # Try to browse into the first item with a URI
        browsable = next((item for item in root_items if item.uri), None)
        if not browsable:
            pytest.skip("No browsable items with URI")

        # Browse into it - should not raise
        sub_items = await client.music.browse(browsable.uri)
        assert sub_items is not None  # May be empty, but should not error
