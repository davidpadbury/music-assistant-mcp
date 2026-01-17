# Contributing

## Development Setup

This project uses [mise](https://mise.jdx.dev/) to manage tools and tasks.

1. Install mise if you haven't already: https://mise.jdx.dev/getting-started.html

2. Clone the repository and trust the mise configuration:
   ```bash
   git clone <repo-url>
   cd music-assistant-skill
   mise trust
   ```

3. Install tools and dependencies:
   ```bash
   mise install
   uv sync
   ```

## Running Checks

Run all checks (lint, format, typecheck, unit tests):

```bash
mise run check
```

Or run individual tasks:

```bash
mise run lint          # Run ruff linter
mise run lint-fix      # Run ruff linter with auto-fix
mise run format        # Format code with ruff
mise run format-check  # Check code formatting
mise run typecheck     # Run ty type checker
mise run test          # Run unit tests
```

## Running Integration Tests

Integration tests run against a real Music Assistant instance. They require:

- A running Music Assistant server
- At least one player configured

Create a `.mise.local.toml` file (git-ignored) with your Music Assistant credentials:

```toml
[env]
MUSIC_ASSISTANT_URL = "http://192.168.1.100:8095"
MUSIC_ASSISTANT_TOKEN = "your-token-here"
```

Then run the integration tests:

```bash
mise run test:integration
```

Integration tests will be skipped if the environment variables are not set.
