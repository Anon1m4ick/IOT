"""
Real implementation of DS2 (Door Sensor / Button) using RPi.GPIO.
The sensor reports "Button Pressed"/"Button Released" events via run_ds2_loop,
matching the simulator behaviour.
"""
import time
import threading
from typing import Optional

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


class DS2:
    """Door sensor / button controller for DS2."""

    def __init__(self, pin: int):
        """
        Initialize button on the given GPIO pin.

        Args:
            pin: BCM GPIO pin number for DS2 (from settings.json).
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")

        self.pin = pin
        self._pressed = False

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # GPIO.add_event_detect(self.pin, GPIO.RISING, callback=self._on_pressed, bouncetime=100)
        # GPIO.add_event_detect(self.pin, GPIO.FALLING, callback=self._on_released, bouncetime=100)
        GPIO.add_event_detect(self.pin, GPIO.BOTH, callback=self._on_edge, bouncetime=100)

    # def _on_pressed(self, channel):
    #     self._pressed = True

    # def _on_released(self, channel):
    #     self._pressed = False

    def _on_edge(self, channel):
        self._pressed = GPIO.input(channel) == GPIO.LOW

    def get_state(self) -> int:
        """
        Return current logical state of the button.

        Returns:
            1 if pressed, 0 if released.
        """
        return 1 if self._pressed else 0

    def cleanup(self):
        """Clean up GPIO resources for this sensor."""
        if GPIO_AVAILABLE:
            try:
                GPIO.remove_event_detect(self.pin)
            except Exception:
                pass
            GPIO.cleanup()


def run_ds2_loop(ds2_instance: DS2, interval: float = 0.1, callback=None, stop_event: Optional[threading.Event] = None):
    """
    Continuous loop that polls DS2 state and calls callback on changes.

    Args:
        ds2_instance: DS2 instance.
        interval: Polling interval in seconds.
        callback: Function called with "Button Pressed"/"Button Released".
        stop_event: threading.Event used to stop the loop.
    """
    if stop_event is None:
        stop_event = threading.Event()

    previous_state = None

    try:
        while not stop_event.is_set():
            current_state = ds2_instance.get_state()

            if previous_state is not None and previous_state != current_state:
                if current_state == 1:
                    if callback:
                        callback("Button Pressed")
                else:
                    if callback:
                        callback("Button Released")

            previous_state = current_state
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[DS2] Stopped by user")
        ds2_instance.cleanup()
    except Exception as e:
        print(f"[DS2] Error: {e}")
        ds2_instance.cleanup()

