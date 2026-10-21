FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for better caching
COPY README.md pyproject.toml uv.lock ./

# Copy application code
COPY src/ src/

# Install dependencies (project installed as editable, src already present)
RUN uv sync --frozen --no-dev

# The container runs as a standalone server by default; set MCP_TRANSPORT=stdio
# to let a client spawn it over standard input/output instead.
ENV MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8844

EXPOSE 8844

CMD ["uv", "run", "--no-dev", "--frozen", "--no-sync", "music-assistant-mcp"]