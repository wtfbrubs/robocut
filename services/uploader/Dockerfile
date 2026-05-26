FROM python:3.11-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY shared/ /shared/
RUN uv pip install --system --no-cache /shared
COPY services/uploader/pyproject.toml .
COPY services/uploader/src ./src
COPY config ./config
RUN uv pip install --system --no-cache redis httpx pyyaml pydantic structlog tenacity
ENV PYTHONPATH=/app
CMD ["python", "-m", "src.main"]
