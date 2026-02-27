"""
Real implementation of BTN (Kitchen Button) using RPi.GPIO.
On press, invokes the registered callback (e.g. 4SD timer add seconds / stop blink).
"""
import threading
import time

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


class BTN:
    """Kitchen button: one GPIO pin, callback on press (RISING edge)."""

    def __init__(self, pin: int, press_callback=None):
        """
        Args:
            pin: BCM GPIO pin number (from settings).
            press_callback: Called on each button press (no arguments).
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")
        self.pin = pin
        self._press_callback = press_callback
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(
            self.pin, GPIO.RISING,
            callback=self._on_press,
            bouncetime=200,
        )

    def _on_press(self, channel):
        if self._press_callback:
            try:
                self._press_callback()
            except Exception as e:
                print(f"[BTN] Callback error: {e}")

    def cleanup(self):
        if GPIO_AVAILABLE:
            try:
                GPIO.remove_event_detect(self.pin)
            except Exception:
                pass
            GPIO.cleanup()


def run_btn_loop(btn: BTN, stop_event: threading.Event):
    """Block until stop_event, then cleanup. Keeps BTN registered while app runs."""
    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    finally:
        btn.cleanup()
