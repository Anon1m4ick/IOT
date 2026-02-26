"""
Real implementation of 4-digit 7-segment display (4SD) using RPi.GPIO.
Based on the user's provided multiplexing example, adapted into a reusable class.
"""
import threading
import time

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


class FourSegmentDisplay:
    _DIGIT_MAP = {
        " ": (0, 0, 0, 0, 0, 0, 0),
        "0": (1, 1, 1, 1, 1, 1, 0),
        "1": (0, 1, 1, 0, 0, 0, 0),
        "2": (1, 1, 0, 1, 1, 0, 1),
        "3": (1, 1, 1, 1, 0, 0, 1),
        "4": (0, 1, 1, 0, 0, 1, 1),
        "5": (1, 0, 1, 1, 0, 1, 1),
        "6": (1, 0, 1, 1, 1, 1, 1),
        "7": (1, 1, 1, 0, 0, 0, 0),
        "8": (1, 1, 1, 1, 1, 1, 1),
        "9": (1, 1, 1, 1, 0, 1, 1),
    }

    def __init__(self, segment_pins, digit_pins, refresh_delay=0.001, decimal_pin=None):
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on Raspberry Pi.")
        self.segment_pins = tuple(segment_pins)
        self.digit_pins = tuple(digit_pins)
        self.refresh_delay = float(refresh_delay)
        self.decimal_pin = decimal_pin
        if len(self.segment_pins) < 7:
            raise ValueError("segment_pins must contain at least 7 segment pins")
        if len(self.digit_pins) != 4:
            raise ValueError("digit_pins must contain exactly 4 pins")

        self._lock = threading.Lock()
        self._text = "    "
        self._colon = False
        self._stop_event = threading.Event()
        self._thread = None

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        for pin in self.segment_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, 0)
        for pin in self.digit_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, 1)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._thread.start()

    def show(self, text: str, colon: bool = True):
        with self._lock:
            self._text = (text or "    ")[:4].rjust(4)
            self._colon = bool(colon)

    def clear(self):
        self.show("    ", colon=False)

    def _refresh_loop(self):
        while not self._stop_event.is_set():
            with self._lock:
                text = self._text
                colon = self._colon
            for digit_index in range(4):
                char = text[digit_index] if digit_index < len(text) else " "
                pattern = self._DIGIT_MAP.get(char, self._DIGIT_MAP[" "])
                for seg_idx in range(7):
                    GPIO.output(self.segment_pins[seg_idx], pattern[seg_idx])
                if self.decimal_pin is not None:
                    GPIO.output(self.decimal_pin, 1 if (colon and digit_index == 1) else 0)
                elif len(self.segment_pins) > 7:
                    GPIO.output(self.segment_pins[7], 1 if (colon and digit_index == 1) else 0)
                GPIO.output(self.digit_pins[digit_index], 0)
                time.sleep(self.refresh_delay)
                GPIO.output(self.digit_pins[digit_index], 1)

    def cleanup(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        try:
            self.clear()
        finally:
            try:
                pins = list(self.segment_pins) + list(self.digit_pins)
                if self.decimal_pin is not None:
                    pins.append(self.decimal_pin)
                GPIO.cleanup(pins)
            except Exception:
                pass
