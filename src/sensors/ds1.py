"""
Real implementation of DS1 (Door Sensor / Button) using RPi.GPIO.
The sensor reports "Button Pressed"/"Button Released" events via run_ds1_loop,
matching the simulator behaviour.
"""
import time
import threading

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


class DS1:
    """Door sensor / button controller for DS1."""

    def __init__(self, pin: int):
        """
        Initialize button on the given GPIO pin.

        Args:
            pin: BCM GPIO pin number for DS1 (from settings.json).
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")

        self.pin = pin
        self._pressed = False

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Edge detection with debouncing, similar to the provided example code.
        GPIO.add_event_detect(self.pin, GPIO.RISING, callback=self._on_pressed, bouncetime=100)
        GPIO.add_event_detect(self.pin, GPIO.FALLING, callback=self._on_released, bouncetime=100)

    def _on_pressed(self, channel):
        self._pressed = True

    def _on_released(self, channel):
        self._pressed = False

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


def run_ds1_loop(ds1_instance: DS1, interval: float = 0.1, callback=None, stop_event: threading.Event | None = None):
    """
    Continuous loop that polls DS1 state and calls callback on changes.

    Args:
        ds1_instance: DS1 instance.
        interval: Polling interval in seconds.
        callback: Function called with "Button Pressed"/"Button Released".
        stop_event: threading.Event used to stop the loop.
    """
    if stop_event is None:
        stop_event = threading.Event()

    previous_state = None

    try:
        while not stop_event.is_set():
            current_state = ds1_instance.get_state()

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
        print("\n[DS1] Stopped by user")
        ds1_instance.cleanup()
    except Exception as e:
        print(f"[DS1] Error: {e}")
        ds1_instance.cleanup()

