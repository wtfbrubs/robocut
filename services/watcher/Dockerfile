FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv yt-dlp yt-dlp-youtube-oauth2
WORKDIR /app
COPY shared/ /shared/
RUN uv pip install --system --no-cache /shared
COPY services/watcher/pyproject.toml .
COPY services/watcher/src ./src
COPY config ./config
RUN uv pip install --system --no-cache httpx yt-dlp pyyaml redis pydantic tenacity structlog
ENV PYTHONPATH=/app
CMD ["python", "-m", "src.main"]
