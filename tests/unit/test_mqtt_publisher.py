import json
import queue
from unittest import mock

import paho.mqtt.client as mqtt
import pytest

from mqtt_publisher import MQTTPublisher


def test_add_sensor_data_enqueues_correct_dict(mqtt_config, device_config):
    pub = MQTTPublisher(mqtt_config, device_config)
    ts = 1234567890.0
    pub.add_sensor_data("DS1", 1, True, timestamp=ts)

    data = pub.data_queue.get_nowait()
    assert data == {
        "sensor_type": "DS1",
        "value": 1,
        "simulated": True,
        "timestamp": ts,
        "pi_id": "PI1",
        "device_name": "TestPi",
    }


def test_add_sensor_data_defaults(mqtt_config):
    pub = MQTTPublisher(mqtt_config, {})
    pub.add_sensor_data("DS2", 0, False)

    data = pub.data_queue.get_nowait()
    assert data["sensor_type"] == "DS2"
    assert data["value"] == 0
    assert data["simulated"] is False
    assert data["pi_id"] == "PI1"
    assert data["device_name"] == "Unknown"
    assert isinstance(data["timestamp"], float)


def test_send_batch_publishes_json_with_simulated_flag(mqtt_config, device_config):
    pub = MQTTPublisher(mqtt_config, device_config)
    pub.client = mock.MagicMock()
    publish_result = mock.MagicMock()
    publish_result.rc = mqtt.MQTT_ERR_SUCCESS
    pub.client.publish.return_value = publish_result
    pub.connection_established.set()

    data = {
        "sensor_type": "DS1",
        "value": 42,
        "simulated": True,
        "timestamp": 99.0,
        "pi_id": "PI1",
        "device_name": "TestPi",
    }
    pub._send_batch([data])

    pub.client.publish.assert_called_once()
    args, kwargs = pub.client.publish.call_args
    topic, payload_json = args
    assert topic == "sensors/ds1"
    assert kwargs.get("qos") == 1

    payload = json.loads(payload_json)
    assert payload == {
        "value": 42,
        "timestamp": 99.0,
        "pi_id": "PI1",
        "device_name": "TestPi",
        "simulated": True,
    }


def test_send_batch_skips_when_not_connected(mqtt_config, device_config):
    pub = MQTTPublisher(mqtt_config, device_config)
    pub.client = mock.MagicMock()

    pub._send_batch([{"sensor_type": "DS1", "value": 1, "simulated": False,
                      "timestamp": 0, "pi_id": "PI1", "device_name": "X"}])

    pub.client.publish.assert_not_called()


def test_send_batch_simulated_false_round_trips(mqtt_config, device_config):
    pub = MQTTPublisher(mqtt_config, device_config)
    pub.client = mock.MagicMock()
    publish_result = mock.MagicMock()
    publish_result.rc = mqtt.MQTT_ERR_SUCCESS
    pub.client.publish.return_value = publish_result
    pub.connection_established.set()

    pub._send_batch([{
        "sensor_type": "DS1",
        "value": 7,
        "simulated": False,
        "timestamp": 1.0,
        "pi_id": "PI1",
        "device_name": "TestPi",
    }])

    payload = json.loads(pub.client.publish.call_args[0][1])
    assert payload["simulated"] is False


def test_reads_batch_config_from_mqtt_config(device_config):
    cfg = {
        "batch_size": 3,
        "batch_interval_seconds": 2,
        "topics": {"DS1": "custom/topic"},
    }
    pub = MQTTPublisher(cfg, device_config)
    assert pub.batch_size == 3
    assert pub.batch_interval == 2
