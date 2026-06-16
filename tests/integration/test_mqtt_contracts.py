import json
import threading
import time
import uuid

import paho.mqtt.client as mqtt
import pytest

from mqtt_publisher import MQTTPublisher

pytestmark = pytest.mark.integration

CONTRACT_KEYS = {"value", "timestamp", "pi_id", "device_name", "simulated"}


def _make_client(client_id):
    return mqtt.Client(
        client_id=client_id,
        protocol=mqtt.MQTTv5,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )


def _wait_for_message(messages, timeout=7.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if messages:
            return messages[0]
        time.sleep(0.1)
    return None


def test_publisher_sensor_contract(broker_available, device_config):
    received = []

    sub = _make_client(f"sub_sensor_{uuid.uuid4().hex[:8]}")
    sub.on_message = lambda cli, userdata, msg: received.append(msg)
    sub.connect("localhost", 1883)
    sub.subscribe("sensors/ds1", qos=1)
    sub.loop_start()
    time.sleep(0.3)

    mqtt_config = {
        "broker_host": "localhost",
        "broker_port": 1883,
        "client_id": f"pub_sensor_{uuid.uuid4().hex[:8]}",
        "batch_size": 1,
        "batch_interval_seconds": 0.2,
        "topics": {"DS1": "sensors/ds1"},
    }
    pub = MQTTPublisher(mqtt_config, device_config)
    try:
        pub.start()
        pub.add_sensor_data("DS1", 1, True)

        msg = _wait_for_message(received, timeout=7.0)
        assert msg is not None, "no MQTT message received on sensors/ds1"

        payload = json.loads(msg.payload.decode("utf-8"))
        assert CONTRACT_KEYS.issubset(payload.keys())
        assert payload["simulated"] is True
        assert payload["value"] == 1
    finally:
        pub.stop()
        sub.loop_stop()
        sub.disconnect()


def test_command_contract_round_trip(broker_available):
    received = []
    control_topic = "commands/pi1"

    sub = _make_client(f"sub_cmd_{uuid.uuid4().hex[:8]}")
    sub.on_message = lambda cli, userdata, msg: received.append(msg)
    sub.connect("localhost", 1883)
    sub.subscribe(control_topic, qos=1)
    sub.loop_start()
    time.sleep(0.3)

    pub = _make_client(f"pub_cmd_{uuid.uuid4().hex[:8]}")
    pub.connect("localhost", 1883)
    pub.loop_start()
    time.sleep(0.2)

    command = {
        "action": "alarm_trigger",
        "payload": {"reason": "test"},
        "source": "web",
        "timestamp": time.time(),
    }
    pub.publish(control_topic, json.dumps(command), qos=1)
    pub.loop_stop()
    pub.disconnect()

    msg = _wait_for_message(received, timeout=5.0)
    assert msg is not None, "no command message received"

    parsed = json.loads(msg.payload.decode("utf-8"))
    assert parsed["action"] == "alarm_trigger"

    sub.loop_stop()
    sub.disconnect()


def test_wrong_broker_host_no_delivery(broker_available, device_config):
    received = []

    sub = _make_client(f"sub_wrong_{uuid.uuid4().hex[:8]}")
    sub.on_message = lambda cli, userdata, msg: received.append(msg)
    sub.connect("localhost", 1883)
    sub.subscribe("sensors/ds1", qos=1)
    sub.loop_start()
    time.sleep(0.3)

    mqtt_config = {
        "broker_host": "10.255.255.1",
        "broker_port": 1883,
        "client_id": f"pub_wrong_{uuid.uuid4().hex[:8]}",
        "batch_size": 1,
        "batch_interval_seconds": 0.2,
        "topics": {"DS1": "sensors/ds1"},
    }
    pub = MQTTPublisher(mqtt_config, device_config)
    try:
        pub.start()
        pub.add_sensor_data("DS1", 99, True)
        time.sleep(3.0)
        assert len(received) == 0, (
            "message arrived on localhost broker but publisher targeted unreachable host"
        )
    finally:
        pub.stop()
        sub.loop_stop()
        sub.disconnect()
