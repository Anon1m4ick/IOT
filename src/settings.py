import json
import os
from typing import Dict


def _apply_env_overrides(settings: Dict) -> Dict:
    """Apply environment variable overrides so the same settings file works
    locally, inside Docker, and on a real Raspberry Pi without code changes.

    On a Pi the broker/server live on another machine, so the publisher must
    target that host instead of ``localhost``. Set ``MQTT_BROKER_HOST`` to the
    server's IP (or ``mosquitto`` inside Docker) to make publishing work.
    """
    mqtt = settings.setdefault("mqtt", {})
    influx = settings.setdefault("influxdb", {})

    broker_host = os.environ.get("MQTT_BROKER_HOST")
    if broker_host:
        mqtt["broker_host"] = broker_host

    broker_port = os.environ.get("MQTT_BROKER_PORT")
    if broker_port:
        try:
            mqtt["broker_port"] = int(broker_port)
        except ValueError:
            pass

    influx_url = os.environ.get("INFLUXDB_URL")
    if influx_url:
        influx["url"] = influx_url

    influx_token = os.environ.get("INFLUXDB_TOKEN")
    if influx_token:
        influx["token"] = influx_token

    influx_org = os.environ.get("INFLUXDB_ORG")
    if influx_org:
        influx["org"] = influx_org

    influx_bucket = os.environ.get("INFLUXDB_BUCKET")
    if influx_bucket:
        influx["bucket"] = influx_bucket

    return settings


def load_settings(filePath: str = 'settings.json') -> Dict:
    with open(filePath, 'r') as f:
        settings = json.load(f)
    return _apply_env_overrides(settings)
