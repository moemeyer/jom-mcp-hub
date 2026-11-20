# Justice Nexus MCP — Cloud Run image (matches jom-mcp-hub server pattern)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY justice-nexus/requirements.txt ./justice-nexus/requirements.txt
RUN pip install --no-cache-dir -r justice-nexus/requirements.txt

COPY justice-nexus/ ./justice-nexus/
COPY oauth/ ./oauth/

ENV PYTHONUNBUFFERED=1
ENV PORT=8002
ENV PYTHONPATH=/app/justice-nexus

WORKDIR /app/justice-nexus

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/" || exit 1

CMD ["python", "server.py"]