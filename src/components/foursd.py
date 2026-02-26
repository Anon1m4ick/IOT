"""
4SD (Kitchen 4-digit 7-segment display) timer component.
Supports simulated and real hardware modes and exposes control handlers for the TUI/web layer.
"""
import threading
import time
from typing import Dict, Optional

from simulators.foursd import FourSegmentDisplaySimulator


def _format_mmss(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}{seconds:02d}"


class FourSDTimerController:
    def __init__(self, settings: Dict, callback=None, mqtt_publisher=None):
        self.settings = settings
        self.callback = callback or (lambda msg: print(f"4SD: {msg}"))
        self.mqtt_publisher = mqtt_publisher
        self.simulated = bool(settings.get("simulated", True))

        self.default_duration = int(settings.get("default_duration_seconds", 60))
        self.button_add_seconds = int(settings.get("button_add_seconds", 30))
        self.tick_interval = float(settings.get("tick_interval", 0.1))
        self.blink_interval = float(settings.get("blink_interval", 0.5))

        self._lock = threading.Lock()
        self._remaining = self.default_duration
        self._running = False
        self._expired_blinking = False
        self._blink_visible = True
        self._last_update_monotonic = time.monotonic()
        self._last_blink_toggle = time.monotonic()
        self._last_render = None
        self._last_reported_remaining = None

        self._display = self._create_display(settings)

    def _create_display(self, settings: Dict):
        if self.simulated:
            return FourSegmentDisplaySimulator()
        from actuators.foursd import FourSegmentDisplay
        segment_pins = settings.get("segment_pins", [11, 4, 23, 8, 7, 10, 18, 25])
        digit_pins = settings.get("digit_pins", [22, 27, 17, 24])
        refresh_delay = settings.get("refresh_delay_seconds", 0.001)
        decimal_pin = settings.get("decimal_pin")
        display = FourSegmentDisplay(segment_pins, digit_pins, refresh_delay, decimal_pin=decimal_pin)
        display.start()
        return display

    def set_duration(self, seconds: int):
        seconds = max(0, int(seconds))
        with self._lock:
            self._remaining = seconds
            self._running = False
            self._expired_blinking = False
            self._blink_visible = True
            self._last_update_monotonic = time.monotonic()
        self.callback(f"Timer set to {seconds}s")
        self._publish_state(force=True)

    def start(self):
        with self._lock:
            self._running = True
            self._expired_blinking = False
            self._blink_visible = True
            self._last_update_monotonic = time.monotonic()
        self.callback("Timer started")
        self._publish_state(force=True)

    def stop(self):
        with self._lock:
            self._running = False
        self.callback("Timer stopped")
        self._publish_state(force=True)

    def add_seconds(self, seconds: Optional[int] = None):
        add_value = self.button_add_seconds if seconds is None else int(seconds)
        stop_blink_only = False
        with self._lock:
            if self._expired_blinking:
                self._expired_blinking = False
                self._blink_visible = True
                stop_blink_only = True
            else:
                self._remaining = max(0, self._remaining + add_value)
                self._last_update_monotonic = time.monotonic()
        if stop_blink_only:
            self.callback("Blinking stopped by BTN")
        else:
            self.callback(f"Added {add_value}s to timer")
        self._publish_state(force=True)

    def button_press(self):
        self.add_seconds(None)

    def set_button_add_seconds(self, seconds: int):
        self.button_add_seconds = max(0, int(seconds))
        self.callback(f"BTN add seconds set to {self.button_add_seconds}")

    def trigger_expired_blink(self):
        with self._lock:
            self._remaining = 0
            self._running = False
            self._expired_blinking = True
            self._blink_visible = True
            self._last_blink_toggle = time.monotonic()
        self.callback("Timer expired - blinking 00:00")
        self._publish_state(force=True)

    def get_state(self) -> Dict:
        with self._lock:
            return {
                "remaining_seconds": int(self._remaining),
                "running": self._running,
                "expired_blinking": self._expired_blinking,
                "button_add_seconds": self.button_add_seconds,
                "simulated": self.simulated,
            }

    def loop(self, stop_event: threading.Event):
        try:
            while not stop_event.is_set():
                self._tick()
                self._render()
                time.sleep(self.tick_interval)
        finally:
            try:
                self._display.clear()
            except Exception:
                pass
            try:
                self._display.cleanup()
            except Exception:
                pass

    def _tick(self):
        now = time.monotonic()
        expired_now = False
        with self._lock:
            if self._running:
                elapsed = now - self._last_update_monotonic
                if elapsed >= 1.0:
                    decrement = int(elapsed)
                    self._remaining = max(0, self._remaining - decrement)
                    self._last_update_monotonic += decrement
                    if self._remaining == 0:
                        self._running = False
                        self._expired_blinking = True
                        self._blink_visible = True
                        self._last_blink_toggle = now
                        expired_now = True

            if self._expired_blinking and (now - self._last_blink_toggle) >= self.blink_interval:
                self._blink_visible = not self._blink_visible
                self._last_blink_toggle = now

        if expired_now:
            self.callback("Timer expired - blinking 00:00")
        self._publish_state()

    def _render(self):
        state = self.get_state()
        text = _format_mmss(state["remaining_seconds"])
        visible = True
        if state["expired_blinking"]:
            with self._lock:
                visible = self._blink_visible
        render_key = (text if visible else "    ", True if visible else False)
        if render_key == self._last_render:
            return
        self._last_render = render_key
        self._display.show(render_key[0], colon=render_key[1])
        self.callback(f"Display {'ON' if visible else 'OFF'} {text[:2]}:{text[2:]}")

    def _publish_state(self, force: bool = False):
        if not self.mqtt_publisher:
            return
        remaining = self.get_state()["remaining_seconds"]
        if not force and remaining == self._last_reported_remaining:
            return
        self._last_reported_remaining = remaining
        self.mqtt_publisher.add_sensor_data("4SD", remaining, self.simulated)


def run_4sd(settings, threads, stop_event, callback=None, mqtt_publisher=None):
    controller = FourSDTimerController(settings, callback=callback, mqtt_publisher=mqtt_publisher)
    thread = threading.Thread(target=controller.loop, args=(stop_event,), daemon=True)
    thread.start()
    threads.append(thread)
    return {
        "set_duration": controller.set_duration,
        "start": controller.start,
        "stop": controller.stop,
        "add_seconds": controller.add_seconds,
        "button_press": controller.button_press,
        "set_button_add_seconds": controller.set_button_add_seconds,
        "trigger_expired_blink": controller.trigger_expired_blink,
        "get_state": controller.get_state,
        "simulated": bool(settings.get("simulated", True)),
    }
