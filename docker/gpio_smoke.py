"""
Docker GPIO/I2C proof script.

This does not simulate real sensor signals. It verifies that the unsimulated
hardware code paths import, initialize, execute representative GPIO/I2C calls,
and clean up inside the Linux iot-app container.
"""
from __future__ import annotations

import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from settings import load_settings


def section(name: str):
    print(f"\n=== {name} ===", flush=True)


def ok(name: str, detail: str = "ok"):
    print(f"[PASS] {name}: {detail}", flush=True)


def run():
    settings = load_settings(os.path.join(ROOT, "settings.json"))

    section("Compatibility modules")
    import RPi.GPIO as GPIO  # type: ignore
    import smbus  # type: ignore

    ok("RPi.GPIO import", f"VERSION={getattr(GPIO, 'VERSION', 'unknown')}")
    bus = smbus.SMBus(1)
    bus.write_byte_data(0x68, 0x6B, 0)
    ok("smbus import/write")

    section("Basic GPIO actuators")
    from components.dl import run_dl
    from components.db import run_db

    dl = run_dl({**settings["DL"], "simulated": False})
    dl["set_state"](1)
    dl["set_state"](0)
    ok("DL real path", f"state={dl['get_state']()}")

    db = run_db({**settings["DB"], "simulated": False})
    db["activate"](1000, 0.05)
    ok("DB real path", "PWM activate 1000Hz/0.05s")

    section("RGB and 7-segment actuators")
    from actuators.brgb import BRGB
    from actuators.foursd import FourSegmentDisplay

    brgb = BRGB(settings["BRGB"]["red_pin"], settings["BRGB"]["green_pin"], settings["BRGB"]["blue_pin"])
    for number in (1, 2, 3, 4, 0):
        brgb.set_color_by_number(number)
    brgb.cleanup()
    ok("BRGB real path", "color GPIO outputs toggled")

    display = FourSegmentDisplay(
        settings["4SD"]["segment_pins"],
        settings["4SD"]["digit_pins"],
        refresh_delay=0.0005,
    )
    display.show("1234")
    display.start()
    time.sleep(0.03)
    display.cleanup()
    ok("4SD real path", "multiplex thread started and cleaned up")

    section("I2C LCD/GSG paths")
    from actuators.lcd import LCD
    from sensors.gsg import GSG

    lcd = LCD(address=settings["LCD"].get("i2c_address"))
    lcd.display_text("GPIO smoke", "LCD path")
    lcd.cleanup()
    ok("LCD real path", "PCF8574/LCD writes executed")

    gsg = GSG(
        threshold=settings["GSG"].get("threshold", 2000),
        calibration_samples=1,
    )
    movement = gsg.detect_movement()
    gsg.cleanup()
    ok("GSG real path", f"detect_movement={movement}")

    section("GPIO input sensors")
    from sensors.ds1 import DS1
    from sensors.ds2 import DS2
    from sensors.dpir1 import DPIR1
    from sensors.dpir2 import DPIR2
    from sensors.dpir3 import DPIR3
    from sensors.dms import DMS
    from sensors.ir import IR

    for name, cls, pin in (
        ("DS1", DS1, settings["DS1"]["pin"]),
        ("DS2", DS2, settings["DS2"]["pin"]),
        ("DPIR1", DPIR1, settings["DPIR1"]["pin"]),
        ("DPIR2", DPIR2, settings["DPIR2"]["pin"]),
        ("DPIR3", DPIR3, settings["DPIR3"]["pin"]),
    ):
        sensor = cls(pin)
        state = sensor.get_state()
        sensor.cleanup()
        ok(f"{name} real path", f"state={state}")

    dms = DMS(rows=settings["DMS"]["rows"], cols=settings["DMS"]["cols"])
    key = dms.read_keypad()
    dms.cleanup()
    ok("DMS real path", f"read_keypad={key!r}")

    ir = IR(settings["IR"]["pin"])
    command = ir.read_command()
    ir.cleanup()
    ok("IR real path", f"read_command={command!r}")

    section("Timing-sensitive sensors without hardware")
    from sensors.dht1 import DHT1, parseCheckCode as parse_dht1
    from sensors.dht2 import DHT2, parseCheckCode as parse_dht2
    from sensors.dht3 import DHT3, parseCheckCode as parse_dht3
    from sensors.dus1 import DUS1
    from sensors.dus2 import DUS2

    for name, cls, parser, pin in (
        ("DHT1", DHT1, parse_dht1, settings["DHT1"]["pin"]),
        ("DHT2", DHT2, parse_dht2, settings["DHT2"]["pin"]),
        ("DHT3", DHT3, parse_dht3, settings["DHT3"]["pin"]),
    ):
        dht = cls(pin)
        code = dht.readDHT11()
        dht.cleanup()
        ok(f"{name} real path", f"readDHT11={parser(code)} (expected without sensor signal)")

    for name, cls, trig, echo in (
        ("DUS1", DUS1, settings["DUS1"]["trig_pin"], settings["DUS1"]["echo_pin"]),
        ("DUS2", DUS2, settings["DUS2"]["trig_pin"], settings["DUS2"]["echo_pin"]),
    ):
        dus = cls(trig, echo)
        distance = dus.get_distance()
        dus.cleanup()
        ok(f"{name} real path", f"get_distance={distance!r} (None/timeout is expected without echo signal)")

    print("\nGPIO/I2C DOCKER SMOKE: PASS", flush=True)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        print("\nGPIO/I2C DOCKER SMOKE: FAIL", flush=True)
        traceback.print_exc()
        sys.exit(1)
