"""
RPi.GPIO-compatible logger for Linux containers without Raspberry Pi GPIO.

This module intentionally lives under docker/rpi_gpio_compat and is enabled by
PYTHONPATH in docker-compose.yml. It lets code configured with simulated:false
exercise the real GPIO branches in a container while printing hardware calls.
"""
from __future__ import annotations

import os
import threading
from collections import defaultdict
from typing import Callable, Iterable

BCM = "BCM"
BOARD = "BOARD"
OUT = "OUT"
IN = "IN"
HIGH = 1
LOW = 0
PUD_UP = "PUD_UP"
PUD_DOWN = "PUD_DOWN"
PUD_OFF = "PUD_OFF"
RISING = "RISING"
FALLING = "FALLING"
BOTH = "BOTH"

VERSION = "docker-compat"

_lock = threading.RLock()
_mode = None
_warnings = True
_pin_modes: dict[int, str] = {}
_pin_values: dict[int, int] = {}
_pin_pulls: dict[int, str | None] = {}
_read_counts: defaultdict[int, int] = defaultdict(int)
_log_counts: defaultdict[tuple[str, int | str], int] = defaultdict(int)
_event_callbacks: defaultdict[int, list[tuple[str, Callable | None, int | None]]] = defaultdict(list)

_verbose = os.getenv("RPI_GPIO_COMPAT_VERBOSE", "").lower() in {"1", "true", "yes", "on"}
_input_pattern = os.getenv("RPI_GPIO_COMPAT_INPUT_PATTERN", "low_then_high").lower()
_log_reads = os.getenv("RPI_GPIO_COMPAT_LOG_READS", "").lower() in {"1", "true", "yes", "on"}


def _log(action: str, detail: str, key: int | str = "global", limit: int = 8) -> None:
    log_key = (action, key)
    _log_counts[log_key] += 1
    count = _log_counts[log_key]
    if not _verbose and count > limit:
        return
    suffix = "" if count <= limit else f" (call {count})"
    print(f"[GPIO-COMPAT] {action}: {detail}{suffix}", flush=True)


def setwarnings(flag: bool) -> None:
    global _warnings
    _warnings = bool(flag)
    _log("setwarnings", str(_warnings))


def setmode(mode) -> None:
    global _mode
    _mode = mode
    _log("setmode", str(mode))


def getmode():
    return _mode


def setup(channel: int | Iterable[int], mode, pull_up_down=None, initial=None) -> None:
    pins = list(channel) if isinstance(channel, (list, tuple, set)) else [channel]
    with _lock:
        for pin in pins:
            pin = int(pin)
            _pin_modes[pin] = mode
            _pin_pulls[pin] = pull_up_down
            if initial is not None:
                _pin_values[pin] = _as_level(initial)
            elif pin not in _pin_values:
                _pin_values[pin] = HIGH if pull_up_down == PUD_UP else LOW
            _log("setup", f"pin={pin} mode={mode} pull={pull_up_down} initial={_pin_values[pin]}", pin)


def output(channel: int | Iterable[int], value) -> None:
    pins = list(channel) if isinstance(channel, (list, tuple, set)) else [channel]
    level = _as_level(value)
    with _lock:
        for pin in pins:
            pin = int(pin)
            old = _pin_values.get(pin)
            _pin_values[pin] = level
            if old != level:
                _log("output", f"pin={pin} value={level}", pin)


def input(channel: int) -> int:
    pin = int(channel)
    with _lock:
        _read_counts[pin] += 1
        count = _read_counts[pin]
        value = _input_value(pin, count)
        _pin_values[pin] = value
    if _verbose or _log_reads:
        _log("input", f"pin={pin} value={value}", pin, limit=3)
    return value


def add_event_detect(channel: int, edge, callback=None, bouncetime=None) -> None:
    pin = int(channel)
    with _lock:
        _event_callbacks[pin].append((edge, callback, bouncetime))
    cb_name = getattr(callback, "__name__", repr(callback)) if callback else None
    _log("add_event_detect", f"pin={pin} edge={edge} bouncetime={bouncetime} callback={cb_name}", pin)


def remove_event_detect(channel: int) -> None:
    pin = int(channel)
    with _lock:
        _event_callbacks.pop(pin, None)
    _log("remove_event_detect", f"pin={pin}", pin)


def event_detected(channel: int) -> bool:
    if _verbose or _log_reads:
        _log("event_detected", f"pin={int(channel)} -> False", int(channel))
    return False


def wait_for_edge(channel: int, edge, timeout=None):
    if _verbose or _log_reads:
        _log("wait_for_edge", f"pin={int(channel)} edge={edge} timeout={timeout} -> None", int(channel))
    return None


def cleanup(channel=None) -> None:
    with _lock:
        if channel is None:
            _pin_modes.clear()
            _pin_values.clear()
            _pin_pulls.clear()
            _read_counts.clear()
            _event_callbacks.clear()
            _log("cleanup", "all")
            return

        pins = list(channel) if isinstance(channel, (list, tuple, set)) else [channel]
        for pin in pins:
            pin = int(pin)
            _pin_modes.pop(pin, None)
            _pin_values.pop(pin, None)
            _pin_pulls.pop(pin, None)
            _read_counts.pop(pin, None)
            _event_callbacks.pop(pin, None)
            _log("cleanup", f"pin={pin}", pin)


class PWM:
    def __init__(self, channel: int, frequency: float):
        self.channel = int(channel)
        self.frequency = float(frequency)
        self.duty_cycle = 0.0
        self.running = False
        _log("PWM.__init__", f"pin={self.channel} frequency={self.frequency}", self.channel)

    def start(self, duty_cycle: float) -> None:
        self.duty_cycle = float(duty_cycle)
        self.running = True
        _log("PWM.start", f"pin={self.channel} duty_cycle={self.duty_cycle}", self.channel)

    def stop(self) -> None:
        self.running = False
        _log("PWM.stop", f"pin={self.channel}", self.channel)

    def ChangeFrequency(self, frequency: float) -> None:
        self.frequency = float(frequency)
        _log("PWM.ChangeFrequency", f"pin={self.channel} frequency={self.frequency}", self.channel)

    def ChangeDutyCycle(self, duty_cycle: float) -> None:
        self.duty_cycle = float(duty_cycle)
        _log("PWM.ChangeDutyCycle", f"pin={self.channel} duty_cycle={self.duty_cycle}", self.channel)


def _as_level(value) -> int:
    return HIGH if bool(value) else LOW


def _input_value(pin: int, count: int) -> int:
    if pin in _pin_values and _pin_modes.get(pin) == OUT:
        return _pin_values[pin]

    if _pin_pulls.get(pin) == PUD_DOWN:
        return LOW

    if _pin_pulls.get(pin) == PUD_UP:
        return HIGH

    if _input_pattern == "static":
        return _pin_values.get(pin, HIGH if _pin_pulls.get(pin) == PUD_UP else LOW)

    if _input_pattern == "toggle":
        return HIGH if (count // 20) % 2 else LOW

    # low_then_high avoids infinite waits in IR/DHT/ultrasonic loops that wait
    # for a low start pulse followed by a high pulse.
    return LOW if count <= 10 else HIGH
