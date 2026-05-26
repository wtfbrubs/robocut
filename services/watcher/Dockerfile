FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl \
    && curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY shared/ /shared/
RUN uv pip install --system --no-cache /shared
COPY services/watcher/pyproject.toml .
COPY services/watcher/src ./src
COPY config ./config
RUN uv pip install --system --no-cache httpx yt-dlp pyyaml redis pydantic tenacity structlog
ENV PYTHONPATH=/app
CMD ["python", "-m", "src.main"]
