import pytest

from main import HeadlessSmartHome


@pytest.fixture
def runner():
    settings = {
        "DL": {"simulated": True, "pin": 17},
        "ALARM": {
            "simulated": True,
            "pin_code": "1234",
            "arming_delay_seconds": 10,
        },
    }
    return HeadlessSmartHome(settings)


def test_dl_set_on(runner):
    runner._handle_remote_command({"action": "dl_set", "payload": {"state": "on"}})
    assert runner.actuators["DL"]["get_state"]() == 1


def test_dl_set_off(runner):
    runner._handle_remote_command({"action": "dl_set", "payload": {"state": "on"}})
    runner._handle_remote_command({"action": "dl_set", "payload": {"state": "off"}})
    assert runner.actuators["DL"]["get_state"]() == 0


def test_alarm_trigger(runner):
    runner._handle_remote_command(
        {"action": "alarm_trigger", "payload": {"reason": "t"}}
    )
    assert runner.alarm_controller.get_state()["alarm_active"] is True


def test_alarm_disarm(runner):
    runner._handle_remote_command(
        {"action": "alarm_trigger", "payload": {"reason": "t"}}
    )
    assert runner.alarm_controller.get_state()["alarm_active"] is True

    runner._handle_remote_command({"action": "alarm_disarm"})
    assert runner.alarm_controller.get_state()["alarm_active"] is False
