import threading
import time
from typing import Dict, List, Optional


DEFAULT_SIMULATION_ORDER = [
    "DUS1",
    "DUS2",
    "DHT1",
    "DHT2",
    "DHT3",
    "LCD",
    "GSG",
    "DS1",
    "DS2",
    "DPIR1",
    "DPIR2",
    "DPIR3",
    "DMS",
]


class SimulatorScheduler:
    def __init__(self, order: List[str], slot_delay_seconds: float, stop_event: threading.Event):
        self.order = list(order)
        self.slot_delay_seconds = max(0.1, float(slot_delay_seconds))
        self.stop_event = stop_event
        self.started_at = time.monotonic()
        self._last_cycle_by_device = {}
        self._lock = threading.Lock()

    def wait_for_turn(self, device_name: str) -> bool:
        if device_name not in self.order:
            return not self.stop_event.wait(self.slot_delay_seconds)

        while not self.stop_event.is_set():
            now = time.monotonic()
            slot_number = int((now - self.started_at) / self.slot_delay_seconds)
            slot_index = slot_number % len(self.order)
            cycle_number = slot_number // len(self.order)

            if self.order[slot_index] == device_name:
                with self._lock:
                    if self._last_cycle_by_device.get(device_name) != cycle_number:
                        self._last_cycle_by_device[device_name] = cycle_number
                        return True

            next_slot_at = self.started_at + ((slot_number + 1) * self.slot_delay_seconds)
            wait_seconds = max(0.02, min(0.2, next_slot_at - time.monotonic()))
            self.stop_event.wait(wait_seconds)

        return False


def build_simulator_scheduler(settings: Dict, stop_event: threading.Event) -> Optional[SimulatorScheduler]:
    simulation_config = settings.get("simulation", {})
    if not isinstance(simulation_config, dict):
        simulation_config = {}

    if simulation_config.get("ordered", True) is False:
        return None

    configured_order = simulation_config.get("order", DEFAULT_SIMULATION_ORDER)
    if not isinstance(configured_order, list):
        configured_order = DEFAULT_SIMULATION_ORDER

    active_order = []
    for device_name in configured_order:
        device_settings = settings.get(device_name)
        if isinstance(device_settings, dict) and device_settings.get("simulated", False):
            active_order.append(device_name)

    if not active_order:
        return None

    slot_delay_seconds = simulation_config.get("slot_delay_seconds", 1.0)
    return SimulatorScheduler(active_order, slot_delay_seconds, stop_event)
