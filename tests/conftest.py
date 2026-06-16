import os
import subprocess
import sys
import threading
import time

import pytest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _try_start_broker():
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "mosquitto"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except Exception:
        pass


def _broker_reachable(host="localhost", port=1883, timeout=2.0):
    import paho.mqtt.client as mqtt

    connected = threading.Event()

    def on_connect(client, userdata, flags, rc, properties=None):
        code = getattr(rc, "getReasonCode", lambda: rc)()
        if code == 0:
            connected.set()

    try:
        client = mqtt.Client(
            client_id="broker_probe",
            protocol=mqtt.MQTTv5,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        client.on_connect = on_connect
        client.connect(host, port, keepalive=60)
        client.loop_start()
        ok = connected.wait(timeout=timeout)
        client.loop_stop()
        client.disconnect()
        return ok
    except Exception:
        return False


@pytest.fixture(scope="session")
def broker_available():
    _try_start_broker()
    time.sleep(1)
    if not _broker_reachable():
        pytest.skip("no broker on localhost:1883")
    return True


@pytest.fixture
def mqtt_config():
    return {
        "broker_host": "localhost",
        "broker_port": 1883,
        "client_id": "test_client",
        "batch_size": 1,
        "batch_interval_seconds": 0.1,
        "topics": {"DS1": "sensors/ds1"},
    }


@pytest.fixture
def device_config():
    return {
        "pi_id": "PI1",
        "device_name": "TestPi",
    }


@pytest.fixture
def alarm_settings():
    return {
        "simulated": True,
        "pin_code": "1234",
        "arming_delay_seconds": 10,
    }


@pytest.fixture
def fake_actuators():
    return {
        "DB": {"activate": lambda *a, **k: None},
        "DL": {
            "set_state": lambda *a, **k: None,
            "get_state": lambda: 0,
        },
    }


@pytest.fixture
def stop_event():
    event = threading.Event()
    yield event
    event.set()
