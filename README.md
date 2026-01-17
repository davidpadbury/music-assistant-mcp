# Music Assistant MCP Server

An MCP (Model Context Protocol) server for controlling [Music Assistant](https://music-assistant.io/) - manage multi-room audio, Sonos speakers, playback queues, and search across music providers.

## Installation

```bash
# Clone and install
git clone https://github.com/davidpadbury/music-assistant-mcp.git
cd music-assistant-mcp
uv sync
```

## Configuration

1. Generate a long-lived token from Music Assistant (Settings > Users > Long-lived access token)

2. Add to Claude Code settings (`~/.claude.json`):

```json
{
  "mcpServers": {
    "music-assistant": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/music-assistant-skill", "music-assistant-mcp"],
      "env": {
        "MUSIC_ASSISTANT_URL": "http://your-server:8095",
        "MUSIC_ASSISTANT_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Quick Start

1. **List available speakers**: Use `ma_list_players` to see all speakers and their current state
2. **Search for music**: Use `ma_search` with a query to find songs, albums, artists, or playlists
3. **Play music**: Use `ma_play_media` with the URI from search results and a player ID
4. **Control playback**: Use `ma_playback` to play, pause, skip, or seek

## Available Tools

### Player Tools

| Tool | Purpose |
|------|---------|
| `ma_list_players` | List all speakers with volume, state, and group info |
| `ma_volume` | Set volume level (0-100), adjust up/down, or mute/unmute |
| `ma_group` | Group speakers together or ungroup them |

### Playback Tools

| Tool | Purpose |
|------|---------|
| `ma_playback` | Control playback: play, pause, stop, toggle, next, previous, seek |
| `ma_play_media` | Play media URIs on a player with queue options (play, replace, next, add) |

### Queue Tools

| Tool | Purpose |
|------|---------|
| `ma_queue` | Get queue contents, set shuffle/repeat, or clear the queue |
| `ma_queue_item` | Move or remove specific items in the queue |

### Music Library Tools

| Tool | Purpose |
|------|---------|
| `ma_search` | Search for artists, albums, tracks, playlists, or radio stations |
| `ma_browse` | Browse music provider content hierarchically |

## Common Workflows

### Play Music on a Speaker

```
1. ma_list_players()                           → Get player IDs
2. ma_search(query="Beatles Abbey Road")       → Find the album, get URI
3. ma_play_media(queue_id="living_room", media="spotify://album/xxx")
```

### Group Speakers for Multi-Room Audio

```
1. ma_list_players()                           → See available speakers
2. ma_group(action="join", player_ids=["kitchen", "bedroom"], target_player_id="living_room")
3. Now all three speakers play in sync
```

### Add to the Current Queue

```
1. ma_search(query="Bohemian Rhapsody", media_types=["track"])
2. ma_play_media(queue_id="living_room", media="spotify://track/xxx", option="add")
```

### Control What's Playing

```
- Pause: ma_playback(queue_id="living_room", command="pause")
- Skip: ma_playback(queue_id="living_room", command="next")
- Volume: ma_volume(player_id="living_room", level=50)
```

## Understanding IDs

- **player_id**: Identifies a speaker (e.g., "sonos_living_room"). Get from `ma_list_players`
- **queue_id**: Usually the same as player_id. Each player has its own queue
- **item_id**: Identifies a track in a queue. Get from `ma_queue`
- **URI**: Identifies a media item (e.g., "spotify://track/abc123"). Get from `ma_search` or `ma_browse`

## Tips

- Always call `ma_list_players` first to discover available speakers and their IDs
- Use `ma_search` to find media before trying to play it
- When grouping speakers, the `target_player_id` becomes the group leader
- Queue IDs are typically the same as player IDs
- Use `option="add"` with `ma_play_media` to add to queue without interrupting current playback
