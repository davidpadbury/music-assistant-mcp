# CLAUDE.md

MCP server that exposes Music Assistant to AI assistants and other MCP clients.

## Making Changes

1. **Read before editing** - Always read relevant files before modifying
2. **Run checks before committing**: `mise run check` (runs lint, format-check, typecheck, test)
3. **Fix issues automatically**: `mise run lint-fix` and `mise run format`
4. **Run integration tests** when changing MCP tools: `mise run test:integration`
   - Requires `.mise.local.toml` with `MUSIC_ASSISTANT_URL` and `MUSIC_ASSISTANT_TOKEN` (see CONTRIBUTING.md)

## Issue Workflow

Issues are tracked at: https://github.com/davidpadbury/music-assistant-mcp/issues

### Picking up an issue

```bash
gh issue list --state open
gh issue view <number>
```

### Working on an issue

1. **Reproduce first** - Use the MCP tools (`ma_list_players`, `ma_search`, etc.) to reproduce the bug before fixing
2. **Implement the fix**
3. **Run checks**: `mise run check`
4. **Ask for review** before committing

### Completing an issue

1. Commit with `Fixes #<number>` in the message to auto-close
2. Push to main
3. Verify issue was closed

## Testing with MCP

You have access to this MCP server's tools. Use them to:
- Verify the server works before changes
- Reproduce reported bugs
- Test fixes after code changes

After editing source files, ask the user to reconnect the MCP server (`/mcp` command) to pick up changes.

## Project Structure

- `src/music_assistant_mcp/` - Main source code
  - `client.py` - Connection management
  - `tools.py` - MCP tool implementations
  - `formatting.py` - Response formatting
- `tests/` - Unit tests
- `integration_tests/` - Tests against real Music Assistant instance

## Reference Documentation

- [Music Assistant](https://www.music-assistant.io/) - Features and capabilities
- [Music Assistant Client](https://github.com/music-assistant/client) - Python client API
