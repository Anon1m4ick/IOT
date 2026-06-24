FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/docker/rpi_gpio_compat:/app/src \
    RPI_GPIO_COMPAT=1

WORKDIR /app

COPY requirements.txt .
RUN grep -v '^RPi\.GPIO' requirements.txt > /tmp/requirements-docker.txt \
    && pip install --no-cache-dir -r /tmp/requirements-docker.txt

COPY . .

CMD ["python", "src/main.py"]
