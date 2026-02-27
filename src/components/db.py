from typing import Dict
import time
from simulators.db import activate_db

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


def run_db(config: Dict):
    """
    Initialize Door Buzzer (DB) actuator.

    In simulated mode (or when GPIO is unavailable) it uses the simulator.
    In real mode it uses PWM on the configured GPIO pin.
    """
    # Fallback to simulator if requested or GPIO is not available
    if config.get("simulated", True) or not GPIO_AVAILABLE:
        return {
            "activate": lambda freq, dur: activate_db(freq, dur),
            "simulated": True,
        }

    pin = int(config.get("pin"))

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)

    # Create PWM object with default frequency; will be changed per call
    pwm = GPIO.PWM(pin, 440)

    def activate(frequency: int, duration: float):
        freq = int(frequency) if frequency else 0
        dur = float(duration) if duration else 0.0
        if freq <= 0 or dur <= 0:
            return

        pwm.ChangeFrequency(freq)
        pwm.start(50)
        try:
            time.sleep(dur)
        finally:
            pwm.stop()

    return {
        "activate": activate,
        "simulated": False,
    }

