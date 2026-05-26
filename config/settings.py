import os

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
CLIP_MAX_DURATION = float(os.environ.get("CLIP_MAX_DURATION", "60"))
CLIP_MIN_DURATION = float(os.environ.get("CLIP_MIN_DURATION", "10"))
CLIP_MIN_SCORE = float(os.environ.get("CLIP_MIN_SCORE", "0.55"))
ENABLE_CAPTIONS = os.environ.get("ENABLE_CAPTIONS", "false").lower() == "true"
CLIPS_BUCKET = os.environ.get("CLIPS_BUCKET", "clipbot-clips")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://minio:9000")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
