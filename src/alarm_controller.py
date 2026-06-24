import threading
import time
from collections import deque
from typing import Callable, Dict, Optional

class AlarmController:
    def __init__(
        self,
        settings: Dict,
        stop_event: threading.Event,
        actuators: Dict,
        mqtt_publisher=None,
        event_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ):
        self.settings = settings or {}
        self.stop_event = stop_event
        self.actuators = actuators
        self.mqtt_publisher = mqtt_publisher
        self.event_callback = event_callback or (lambda message: print(f"[ALARM] {message}"))
        self.status_callback = status_callback or (lambda message: None)
        self.simulated = bool(self.settings.get("simulated", True))

        self.pin_code = str(self.settings.get("pin_code", "1234"))
        self.arming_delay_seconds = float(self.settings.get("arming_delay_seconds", 10))
        self.ds_open_timeout_seconds = float(self.settings.get("ds_open_timeout_seconds", 5))
        self.dl_motion_seconds = float(self.settings.get("dl_motion_seconds", 10))
        self.dus_history_seconds = float(self.settings.get("dus_history_seconds", 5))
        self.siren_frequency = int(self.settings.get("siren_frequency_hz", 1000))
        self.siren_pulse_duration = float(self.settings.get("siren_pulse_duration_seconds", 0.5))
        self.siren_pause = float(self.settings.get("siren_pause_seconds", 0.5))
        self.pir_person_count_alarm = bool(self.settings.get("pir_no_person_triggers_alarm", True))

        self._lock = threading.Lock()
        self._alarm_active = False
        self._alarm_reason = ""
        self._security_armed = False
        self._arming_deadline = None
        self._person_count = 0
        self._pin_buffer = ""
        self._ds_state = {"DS1": 0, "DS2": 0}
        self._ds_pressed_since = {"DS1": None, "DS2": None}
        self._ds_timeout_alarm_sensors = set()
        self._dl_off_deadline = None
        self._dus_history = {"DUS1": deque(), "DUS2": deque()}
        self._siren_stop_event = threading.Event()
        self._siren_thread = None
        self._last_published_person_count = None

    def start(self, threads):
        worker = threading.Thread(target=self._worker_loop, daemon=True)
        worker.start()
        threads.append(worker)
        self._publish_people_count(self._person_count)
        self._publish_security_state()

    def get_state(self) -> Dict:
        with self._lock:
            return {
                "alarm_active": self._alarm_active,
                "security_armed": self._security_armed,
                "arming_in_progress": self._arming_deadline is not None,
                "person_count": self._person_count,
                "pin_buffer": self._pin_buffer,
                "reason": self._alarm_reason,
                "simulated": self.simulated,
            }

    def arm(self):
        with self._lock:
            self._arming_deadline = time.monotonic() + self.arming_delay_seconds
            self._pin_buffer = ""
        self._emit(f"Security arming started ({int(self.arming_delay_seconds)}s delay)")
        self._publish_security_state()

    def disarm(self):
        with self._lock:
            was_alarm = self._alarm_active
            self._security_armed = False
            self._arming_deadline = None
            self._pin_buffer = ""
            self._alarm_active = False
            self._alarm_reason = ""
            self._ds_timeout_alarm_sensors.clear()
        if was_alarm:
            self._stop_siren()
            self._publish_alarm_state(0)
        self._emit("Security disarmed")
        self._publish_security_state()
        self._publish_alarm_reason("")

    def trigger_alarm(self, reason: str):
        self._activate_alarm(reason)

    def handle_ds(self, sensor_name: str, state: int):
        state = 1 if int(state) else 0
        now = time.monotonic()
        should_clear_unlocked_alarm = False
        with self._lock:
            previous = self._ds_state.get(sensor_name, 0)
            self._ds_state[sensor_name] = state
            if state == 1 and previous == 0:
                self._ds_pressed_since[sensor_name] = now
                armed = self._security_armed
            elif state == 0:
                self._ds_pressed_since[sensor_name] = None
                armed = False
                if sensor_name in self._ds_timeout_alarm_sensors:
                    self._ds_timeout_alarm_sensors.discard(sensor_name)
                    should_clear_unlocked_alarm = not self._ds_timeout_alarm_sensors and self._alarm_active
            else:
                armed = False
        if state != previous:
            self._emit(f"{sensor_name} {'ACTIVE' if state else 'INACTIVE'}")
        if state == 0 and should_clear_unlocked_alarm:
            self._deactivate_alarm(f"{sensor_name} changed state")
        if armed:
            self._activate_alarm(f"{sensor_name} triggered while system armed")

    def handle_dus(self, sensor_name: str, distance_value):
        if not isinstance(distance_value, (int, float)):
            return
        now = time.monotonic()
        with self._lock:
            history = self._dus_history.setdefault(sensor_name, deque())
            history.append((now, float(distance_value)))
            self._prune_history_locked(history, now)

    def handle_pir(self, sensor_name: str):
        now = time.monotonic()
        self._emit(f"{sensor_name} motion detected")

        turn_on_dl = sensor_name == "DPIR1"
        if turn_on_dl:
            with self._lock:
                self._dl_off_deadline = now + self.dl_motion_seconds
            self._set_dl(1)

        delta = None
        if sensor_name in ("DPIR1", "DPIR2"):
            with self._lock:
                dus_name = "DUS1" if sensor_name == "DPIR1" else "DUS2"
                delta = self._infer_person_delta_locked(dus_name, sensor_name, now)
                if delta is not None:
                    self._person_count = max(0, self._person_count + delta)
                    count = self._person_count
                else:
                    count = self._person_count
        else:
            count = self.get_state()["person_count"]

        if delta == 1:
            self._emit(f"Person ENTER inferred by {sensor_name}; count={count}")
        elif delta == -1:
            self._emit(f"Person EXIT inferred by {sensor_name}; count={count}")

        self._publish_people_count(count)

        if self.pir_person_count_alarm and count == 0 and sensor_name in ("DPIR1", "DPIR2", "DPIR3"):
            self._activate_alarm(f"{sensor_name} motion while person_count=0")

    def handle_gsg(self, value: int):
        if int(value) == 1:
            self._emit("GSG significant movement detected")
            self._activate_alarm("GSG significant movement")

    def handle_dms_key(self, key: str):
        key = str(key).strip().upper()
        if not key:
            return
        if key.isdigit():
            auto_submit = False
            masked = ""
            with self._lock:
                if len(self._pin_buffer) < 4:
                    self._pin_buffer += key
                auto_submit = len(self._pin_buffer) == 4
                masked = "*" * len(self._pin_buffer)
            self._emit(f"DMS PIN input: {masked}")
            if auto_submit:
                self._submit_pin()
            return
        if key == "*":
            with self._lock:
                self._pin_buffer = ""
            self._emit("DMS PIN buffer cleared")
            return
        if key == "#":
            self._submit_pin()
            return
        if key == "A":
            self.arm()
            return
        if key == "B":
            self.disarm()
            return
        if key == "D":
            self._activate_alarm("Manual DMS trigger")
            return
        self._emit(f"DMS key ignored: {key}")

    def _submit_pin(self):
        with self._lock:
            pin = self._pin_buffer
            self._pin_buffer = ""
            alarm_active = self._alarm_active
            armed_or_arming = self._security_armed or (self._arming_deadline is not None)
        if len(pin) != 4:
            self._emit("PIN submit ignored (need 4 digits)")
            return
        if pin == self.pin_code:
            if alarm_active or armed_or_arming:
                self.disarm()
                self._emit("Correct PIN entered: alarm/system disabled")
            else:
                self.arm()
                self._emit("Correct PIN entered: arming scheduled")
        else:
            self._emit("Wrong PIN")
            if armed_or_arming:
                self._activate_alarm("Wrong PIN while armed/arming")

    def _worker_loop(self):
        while not self.stop_event.is_set():
            now = time.monotonic()
            arm_completed = False
            alarm_reasons = []
            turn_dl_off = False

            with self._lock:
                if self._arming_deadline is not None and now >= self._arming_deadline:
                    self._security_armed = True
                    self._arming_deadline = None
                    arm_completed = True
                for name, since in self._ds_pressed_since.items():
                    if isinstance(since, (int, float)) and (now - since) >= self.ds_open_timeout_seconds:
                        self._ds_pressed_since[name] = "triggered"
                        self._ds_timeout_alarm_sensors.add(name)
                        alarm_reasons.append(f"{name} active > {int(self.ds_open_timeout_seconds)}s (door unlocked)")
                if self._dl_off_deadline is not None and now >= self._dl_off_deadline:
                    self._dl_off_deadline = None
                    turn_dl_off = True

            if arm_completed:
                self._emit("Security system ARMED")
                self._publish_security_state()
            for reason in alarm_reasons:
                self._activate_alarm(reason)
            if turn_dl_off:
                self._set_dl(0)
            time.sleep(0.1)

        self._stop_siren()

    def _infer_person_delta_locked(self, dus_name: str, pir_name: str, now: float):
        history = self._dus_history.get(dus_name)
        if not history:
            return None
        self._prune_history_locked(history, now)
        if len(history) < 3:
            return None
        values = [v for _, v in history]
        mid = len(values) // 2
        first_avg = sum(values[:mid]) / max(1, len(values[:mid]))
        second_avg = sum(values[mid:]) / max(1, len(values[mid:]))
        trend_increasing = second_avg > first_avg
        key = f"{pir_name.lower()}_entry_on_increasing"
        entry_on_increasing = bool(self.settings.get(key, True if pir_name == "DPIR1" else False))
        entering = trend_increasing if entry_on_increasing else (not trend_increasing)
        return 1 if entering else -1

    def _prune_history_locked(self, history: deque, now: float):
        while history and (now - history[0][0]) > self.dus_history_seconds:
            history.popleft()

    def _activate_alarm(self, reason: str):
        with self._lock:
            if self._alarm_active:
                self._alarm_reason = reason
                already_active = True
            else:
                self._alarm_active = True
                self._alarm_reason = reason
                already_active = False
        if already_active:
            self._publish_alarm_reason(reason)
            return
        self._emit(f"ALARM ACTIVATED: {reason}")
        self._start_siren()
        self._publish_alarm_state(1)
        self._publish_alarm_reason(reason)
        self._publish_security_state()

    def _deactivate_alarm(self, reason: str):
        with self._lock:
            if not self._alarm_active:
                return
            self._alarm_active = False
            self._alarm_reason = ""
        self._stop_siren()
        self._emit(f"ALARM DEACTIVATED: {reason}")
        self._publish_alarm_state(0)
        self._publish_alarm_reason("")
        self._publish_security_state()

    def _start_siren(self):
        if "DB" not in self.actuators:
            return
        if self._siren_thread and self._siren_thread.is_alive():
            return
        self._siren_stop_event.clear()

        def siren_loop():
            while not self.stop_event.is_set() and not self._siren_stop_event.is_set():
                if not self.get_state()["alarm_active"]:
                    break
                try:
                    self.actuators["DB"]["activate"](self.siren_frequency, self.siren_pulse_duration)
                except Exception as exc:
                    self._emit(f"Siren error: {exc}")
                    break
                sleep_until = time.monotonic() + self.siren_pause
                while time.monotonic() < sleep_until:
                    if self.stop_event.is_set() or self._siren_stop_event.is_set():
                        return
                    time.sleep(0.05)

        self._siren_thread = threading.Thread(target=siren_loop, daemon=True)
        self._siren_thread.start()

    def _stop_siren(self):
        self._siren_stop_event.set()
        if self._siren_thread:
            self._siren_thread.join(timeout=1.0)

    def _set_dl(self, state: int):
        actuator = self.actuators.get("DL")
        if not actuator:
            return
        try:
            actuator["set_state"](1 if state else 0)
            self._emit(f"DL {'ON' if state else 'OFF'} (alarm logic)")
            if self.mqtt_publisher:
                self.mqtt_publisher.add_sensor_data("DL", int(1 if state else 0), actuator.get("simulated", True))
        except Exception as exc:
            self._emit(f"DL control error: {exc}")

    def _publish_alarm_state(self, state: int):
        if self.mqtt_publisher:
            self.mqtt_publisher.add_sensor_data("ALARM", int(state), self.simulated)

    def _publish_alarm_reason(self, reason: str):
        if self.mqtt_publisher:
            self.mqtt_publisher.add_sensor_data("ALARM_REASON", str(reason), self.simulated)

    def _publish_security_state(self):
        if not self.mqtt_publisher:
            return
        with self._lock:
            armed = 1 if self._security_armed else 0
            arming = 1 if self._arming_deadline is not None else 0
        self.mqtt_publisher.add_sensor_data("ALARM_ARMED", armed, self.simulated)
        self.mqtt_publisher.add_sensor_data("ALARM_ARMING", arming, self.simulated)

    def _publish_people_count(self, count: int):
        if not self.mqtt_publisher:
            return
        count = max(0, int(count))
        if self._last_published_person_count == count:
            return
        self._last_published_person_count = count
        self.mqtt_publisher.add_sensor_data("ALARM_PEOPLE", count, self.simulated)

    def _emit(self, message: str):
        try:
            self.event_callback(message)
        except Exception:
            pass
        try:
            self.status_callback(message)
        except Exception:
            pass
