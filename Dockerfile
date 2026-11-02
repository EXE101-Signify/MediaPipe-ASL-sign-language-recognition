FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=2

WORKDIR /app

# opencv-python and MediaPipe wheels need these shared libraries on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt 'gunicorn>=22,<24'

COPY api.py preprocessing.py realtime_translator.py motion.py smoothing.py ui.py class_names.txt /app/

RUN useradd --system --uid 10001 --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).close()" || exit 1

# One worker loads one copy of the ONNX model; four threads share its inference lock.
CMD ["sh", "-c", "test -r /app/asl_cnn_model.onnx && test -s /app/asl_cnn_model.onnx || { echo 'Model missing, unreadable, or empty' >&2; exit 1; }; exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 2 --timeout 60 --graceful-timeout 30 --access-logfile - --error-logfile - 'api:create_app()'"]
