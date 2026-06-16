# Single image used for both the headless PI app (main.py) and the Flask server.
# RPi.GPIO is intentionally NOT installed: in simulated mode it is never
# imported, and it cannot be built off a real Raspberry Pi (e.g. on arm64/amd64
# Linux containers). Set the run command per service in docker-compose.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Runtime dependencies (kept in sync with requirements.txt minus RPi.GPIO).
RUN pip install --no-cache-dir \
    textual \
    paho-mqtt \
    flask \
    influxdb-client

COPY src/ ./src/
COPY docker/ ./docker/
COPY settings.json ./settings.json

# Default to the headless PI app; docker-compose overrides per service.
CMD ["python", "src/main.py", "--headless"]
