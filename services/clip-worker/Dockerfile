FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY shared/ /shared/
RUN uv pip install --system --no-cache /shared
COPY services/clip-worker/pyproject.toml .
COPY services/clip-worker/src ./src
COPY config ./config
RUN uv pip install --system --no-cache redis ffmpeg-python pydantic structlog tenacity pyyaml
ENV PYTHONPATH=/app
CMD ["python", "-m", "src.main"]
