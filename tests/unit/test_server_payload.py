import pytest

from server import MQTTInfluxDBBridge


@pytest.fixture
def bridge():
    return MQTTInfluxDBBridge(
        mqtt_config={"topics": {}, "control_topic": "commands/pi1"},
        influxdb_config={
            "bucket": "NTP",
            "org": "FTN",
            "url": "http://x",
            "token": "t",
        },
    )


def test_convert_value_numeric(bridge):
    assert bridge._convert_value(5) == 5.0
    assert bridge._convert_value("1.5") == 1.5


def test_convert_value_non_numeric_string(bridge):
    result = bridge._convert_value("abc")
    assert isinstance(result, float)


def test_convert_dms_value(bridge):
    assert bridge._convert_dms_value("A") == 10.0
    assert bridge._convert_dms_value("5") == 5.0
    assert bridge._convert_dms_value("#") == 15.0


def test_update_runtime_state_alarm(bridge):
    bridge._update_runtime_state("ALARM", {"value": 1, "timestamp": 0})
    dashboard = bridge.get_dashboard_state()
    assert dashboard["state"]["alarm_active"] is True
    assert len(dashboard["notifications"]) > 0


def test_update_runtime_state_4sd_timer(bridge):
    bridge._update_runtime_state("4SD", {"value": 42, "timestamp": 0})
    assert bridge.state["timer_remaining_seconds"] == 42
