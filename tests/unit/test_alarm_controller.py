import threading
import time

import pytest

from alarm_controller import AlarmController


@pytest.fixture
def controller(alarm_settings, fake_actuators, stop_event):
    return AlarmController(
        alarm_settings,
        stop_event,
        fake_actuators,
    )


def test_gsg_triggers_alarm(controller):
    controller.handle_gsg(1)
    assert controller.get_state()["alarm_active"] is True


def test_pir_motion_with_zero_person_count_triggers_alarm(controller):
    controller.handle_pir("DPIR3")
    assert controller.get_state()["alarm_active"] is True


def test_pin_arm_schedules_arming(controller):
    for digit in "1234":
        controller.handle_dms_key(digit)
    assert controller.get_state()["arming_in_progress"] is True


def test_pin_disarm_clears_alarm(controller):
    controller.trigger_alarm("test reason")
    assert controller.get_state()["alarm_active"] is True

    for digit in "1234":
        controller.handle_dms_key(digit)

    assert controller.get_state()["alarm_active"] is False


def test_ds_open_timeout_triggers_alarm(fake_actuators, stop_event):
    settings = {
        "simulated": True,
        "pin_code": "1234",
        "ds_open_timeout_seconds": 0.2,
    }
    c = AlarmController(settings, stop_event, fake_actuators)
    threads = []
    c.start(threads=threads)

    c.handle_ds("DS1", 1)
    time.sleep(0.4)

    assert c.get_state()["alarm_active"] is True

    stop_event.set()
    for t in threads:
        t.join(timeout=2)
