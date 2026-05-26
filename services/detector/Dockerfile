FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY shared/ /shared/
RUN uv pip install --system --no-cache /shared
COPY services/detector/pyproject.toml .
COPY services/detector/src ./src
RUN uv pip install --system --no-cache redis pyyaml pydantic structlog tenacity numpy
ENV PYTHONPATH=/app
CMD ["python", "-m", "src.main"]
