import json
import os
from typing import Dict


def _env_first(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _apply_env_overrides(settings: Dict) -> Dict:
    """Override infrastructure endpoints without changing device simulation flags."""
    mqtt = settings.get("mqtt")
    if isinstance(mqtt, dict):
        broker_host = _env_first("IOT_MQTT_HOST", "MQTT_BROKER_HOST")
        if broker_host:
            mqtt["broker_host"] = broker_host

        broker_port = _env_first("IOT_MQTT_PORT", "MQTT_BROKER_PORT")
        if broker_port:
            mqtt["broker_port"] = int(broker_port)

    influxdb = settings.get("influxdb")
    if isinstance(influxdb, dict):
        influx_url = _env_first("IOT_INFLUXDB_URL", "INFLUXDB_URL")
        if influx_url:
            influxdb["url"] = influx_url

        influx_token = _env_first("IOT_INFLUXDB_TOKEN", "INFLUXDB_TOKEN")
        if influx_token:
            influxdb["token"] = influx_token

        influx_org = _env_first("IOT_INFLUXDB_ORG", "INFLUXDB_ORG")
        if influx_org:
            influxdb["org"] = influx_org

        influx_bucket = _env_first("IOT_INFLUXDB_BUCKET", "INFLUXDB_BUCKET")
        if influx_bucket:
            influxdb["bucket"] = influx_bucket

    return settings


def load_settings(filePath: str = "settings.json") -> Dict:
    with open(filePath, "r", encoding="utf-8") as f:
        settings = json.load(f)
    return _apply_env_overrides(settings)
