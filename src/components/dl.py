from typing import Dict
from simulators.dl import set_dl_state, get_dl_state

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


def run_dl(config: Dict):
    """
    Initialize Door Light (DL) actuator.

    In simulated mode (or when GPIO is unavailable) it uses the simulator.
    In real mode it controls a GPIO output pin specified in config["pin"].
    """
    # Fallback to simulator if requested or GPIO is not available
    if config.get("simulated", True) or not GPIO_AVAILABLE:
        return {
            "set_state": lambda state: set_dl_state(state),
            "get_state": get_dl_state,
            "simulated": True,
        }

    pin = int(config.get("pin"))

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)

    state_holder = {"value": 0}

    def set_state(state: int):
        value = 1 if int(state) else 0
        GPIO.output(pin, GPIO.HIGH if value else GPIO.LOW)
        state_holder["value"] = value

    def get_state():
        return state_holder["value"]

    return {
        "set_state": set_state,
        "get_state": get_state,
        "simulated": False,
    }

