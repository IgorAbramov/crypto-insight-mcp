# crypto-insight-mcp — REST gateway image.
# The MCP server itself is a stdio process and is normally launched directly
# by the MCP client (e.g. Claude Desktop); see docker-compose.yml for an
# example of running it in a container instead.

FROM python:3.11-slim

WORKDIR /app

# Install the package first so Docker layer caching works for code changes.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY knowledge_base ./knowledge_base

ENV CIM_CHROMA_DIR=/data/chroma
VOLUME ["/data/chroma"]

EXPOSE 8000

# Build the knowledge-base index on start if missing, then serve the API.
CMD ["sh", "-c", "python -m crypto_insight_mcp.rag.ingest && uvicorn crypto_insight_mcp.api:app --host 0.0.0.0 --port 8000"]
