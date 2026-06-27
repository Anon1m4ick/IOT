import json
import os
import sys
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt

from alarm_controller import AlarmController
from components.brgb import run_brgb
from components.btn import run_btn
from components.camera import run_camera
from components.db import run_db
from components.dht1 import run_dht1
from components.dht2 import run_dht2
from components.dht3 import run_dht3
from components.dl import run_dl
from components.dms import run_dms
from components.dpir1 import run_dpir1
from components.dpir2 import run_dpir2
from components.dpir3 import run_dpir3
from components.ds1 import run_ds1
from components.ds2 import run_ds2
from components.dus1 import run_dus1
from components.dus2 import run_dus2
from components.foursd import run_4sd
from components.gsg import run_gsg
from components.ir import run_ir
from components.lcd import run_lcd
from mqtt_publisher import MQTTPublisher
from settings import load_settings
from simulator_scheduler import build_simulator_scheduler


SENSOR_TO_PI = {
    "DS1": "PI1", "DL": "PI1", "DUS1": "PI1", "DB": "PI1", "DPIR1": "PI1", "DMS": "PI1",
    "CAMERA": "PI1", "DS2": "PI2", "DUS2": "PI2", "DPIR2": "PI2", "4SD": "PI2",
    "BTN": "PI2", "DHT3": "PI2", "GSG": "PI2", "DHT1": "PI3", "DHT2": "PI3",
    "IR": "PI3", "BRGB": "PI3", "LCD": "PI3", "DPIR3": "PI3", "ALARM": "PI1",
    "SYSTEM": "PI1",
}

BRGB_COLOR_TO_BUTTON = {
    "OFF": "0",
    "WHITE": "1",
    "RED": "2",
    "GREEN": "3",
    "BLUE": "4",
    "YELLOW": "5",
    "PURPLE": "6",
    "LIGHT_BLUE": "7",
}


def log_line(sensor_name: str, message: str, pi: Optional[str] = None):
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    owner = pi or SENSOR_TO_PI.get(sensor_name, "PI1")
    print(f"{timestamp} [{owner}] {sensor_name:<8} {message}", flush=True)


class SmartHomeRuntime:
    def __init__(self, settings):
        self.settings = settings
        self.threads = []
        self.stop_event = threading.Event()
        self.actuators = {}
        self.mqtt_publisher = None
        self.control_mqtt_client = None
        self.control_topic = "commands/pi1"
        self.brgb_handler = None
        self.alarm_controller = None
        self.simulator_scheduler = build_simulator_scheduler(settings, self.stop_event)

        self._init_actuators()
        self._init_mqtt_publisher()
        self._init_alarm_controller()

    def start(self):
        log_line("SYSTEM", "Starting SmartHome headless runtime")
        self._start_sensors()
        self._publish_initial_runtime_state()
        self._start_control_listener()
        log_line("SYSTEM", "Runtime ready. Logs are printed to stdout.")

    def run_forever(self):
        self.start()
        try:
            while not self.stop_event.wait(1):
                pass
        finally:
            self.shutdown()

    def shutdown(self):
        if self.stop_event.is_set():
            log_line("SYSTEM", "Shutting down")
        self.stop_event.set()
        self._stop_control_listener()
        if self.mqtt_publisher:
            self.mqtt_publisher.stop()
        for thread in self.threads:
            thread.join(timeout=2)
        log_line("SYSTEM", "Runtime stopped")

    def _init_actuators(self):
        if "DL" in self.settings:
            self.actuators["DL"] = run_dl(self.settings["DL"])
            log_line("DL", f"Initialized ({'simulated' if self.actuators['DL'].get('simulated', True) else 'real'})")

        if "DB" in self.settings:
            self.actuators["DB"] = run_db(self.settings["DB"])
            log_line("DB", f"Initialized ({'simulated' if self.actuators['DB'].get('simulated', True) else 'real'})")

        if "CAMERA" in self.settings:
            self.actuators["CAMERA"] = run_camera(
                self.settings["CAMERA"],
                self.threads,
                self.stop_event,
                callback=lambda message: self._log("CAMERA", message),
            )

    def _init_mqtt_publisher(self):
        mqtt_config = self.settings.get("mqtt")
        if not mqtt_config:
            log_line("MQTT", "MQTT configuration not found; publishing disabled", "SYSTEM")
            return

        try:
            self.mqtt_publisher = MQTTPublisher(mqtt_config, self.settings.get("device", {}))
            self.mqtt_publisher.start()
            log_line("MQTT", "Publisher initialized", "SYSTEM")
        except Exception as exc:
            self.mqtt_publisher = None
            log_line("MQTT", f"Publisher initialization failed: {exc}", "SYSTEM")

    def _init_alarm_controller(self):
        if "ALARM" not in self.settings:
            return
        self.alarm_controller = AlarmController(
            self.settings["ALARM"],
            self.stop_event,
            self.actuators,
            mqtt_publisher=self.mqtt_publisher,
            event_callback=lambda message: self._log("ALARM", message),
        )

    def _start_control_listener(self):
        mqtt_config = self.settings.get("mqtt")
        if not mqtt_config:
            return

        broker_host = mqtt_config.get("broker_host", "localhost")
        broker_port = int(mqtt_config.get("broker_port", 1883))
        base_client_id = mqtt_config.get("client_id", "pi1_client")
        self.control_topic = str(mqtt_config.get("control_topic", "commands/pi1"))

        try:
            client = mqtt.Client(
                client_id=f"{base_client_id}_control_listener",
                protocol=mqtt.MQTTv5,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )

            def on_connect(cli, userdata, flags, rc, properties=None):
                code = getattr(rc, "getReasonCode", lambda: rc)()
                if code == 0:
                    cli.subscribe(self.control_topic, qos=1)
                    log_line("MQTT", f"Subscribed to web control topic: {self.control_topic}", "SYSTEM")
                else:
                    log_line("MQTT", f"Control listener connect error: {code}", "SYSTEM")

            def on_message(cli, userdata, msg):
                try:
                    payload = json.loads(msg.payload.decode("utf-8"))
                    if isinstance(payload, dict):
                        self._handle_remote_command(payload)
                except Exception as exc:
                    log_line("MQTT", f"Invalid control message: {exc}", "SYSTEM")

            client.on_connect = on_connect
            client.on_message = on_message
            client.connect(broker_host, broker_port, keepalive=60)
            client.loop_start()
            self.control_mqtt_client = client
        except Exception as exc:
            log_line("MQTT", f"Failed to start control listener: {exc}", "SYSTEM")

    def _stop_control_listener(self):
        if not self.control_mqtt_client:
            return
        try:
            self.control_mqtt_client.loop_stop()
            self.control_mqtt_client.disconnect()
        except Exception:
            pass
        finally:
            self.control_mqtt_client = None

    def _publish_runtime_value(self, sensor_type: str, value, simulated: bool = True):
        if self.mqtt_publisher:
            self.mqtt_publisher.add_sensor_data(sensor_type, value, simulated)

    def _publish_dl_state(self):
        actuator = self.actuators.get("DL")
        if not actuator:
            return
        try:
            self._publish_runtime_value("DL", int(actuator["get_state"]()), actuator.get("simulated", True))
        except Exception:
            pass

    def _publish_camera_state(self):
        actuator = self.actuators.get("CAMERA")
        if not actuator:
            return
        try:
            self._publish_runtime_value("CAMERA_STATUS", actuator["get_state"](), actuator.get("simulated", False))
        except Exception:
            pass

    def _publish_initial_runtime_state(self):
        self._publish_dl_state()
        self._publish_camera_state()
        if "BRGB" in self.settings:
            self._publish_runtime_value("BRGB", "OFF", self.settings["BRGB"].get("simulated", True))

    def _handle_remote_command(self, command: dict):
        action = str(command.get("action", "")).strip().lower()
        payload = command.get("payload", {})
        payload = payload if isinstance(payload, dict) else {}
        if not action:
            return

        log_line("COMMAND", f"{action} {payload}", "SYSTEM")

        try:
            if action == "alarm_arm" and self.alarm_controller:
                self.alarm_controller.arm()
            elif action == "alarm_disarm" and self.alarm_controller:
                self.alarm_controller.disarm()
            elif action == "alarm_trigger" and self.alarm_controller:
                self.alarm_controller.trigger_alarm(str(payload.get("reason", "Web trigger")))
            elif action == "alarm_pin" and self.alarm_controller:
                pin = str(payload.get("pin", "")).strip()
                if pin.isdigit() and len(pin) == 4:
                    for char in pin:
                        self.alarm_controller.handle_dms_key(char)
            elif action == "timer_set" and "4SD" in self.actuators:
                self.actuators["4SD"]["set_duration"](int(payload.get("seconds", 60)))
            elif action == "timer_start" and "4SD" in self.actuators:
                self.actuators["4SD"]["start"]()
            elif action == "timer_stop" and "4SD" in self.actuators:
                self.actuators["4SD"]["stop"]()
            elif action == "timer_add" and "4SD" in self.actuators:
                seconds = payload.get("seconds")
                self.actuators["4SD"]["add_seconds"](None if seconds is None else int(seconds))
            elif action == "timer_button" and "4SD" in self.actuators:
                self.actuators["4SD"]["button_press"]()
                self._publish_runtime_value("BTN", 1, self.settings.get("BTN", {}).get("simulated", True))
                log_line("BTN", "Web/demo press")
            elif action == "timer_set_button_add" and "4SD" in self.actuators:
                self.actuators["4SD"]["set_button_add_seconds"](int(payload.get("seconds", 30)))
            elif action == "timer_blink" and "4SD" in self.actuators:
                self.actuators["4SD"]["trigger_expired_blink"]()
            elif action == "brgb_button":
                self._handle_brgb_button(str(payload.get("button", "")).strip())
            elif action == "brgb_color":
                color = str(payload.get("color", "")).strip().upper()
                self._handle_brgb_button(BRGB_COLOR_TO_BUTTON.get(color, ""))
            elif action == "dl_set" and "DL" in self.actuators:
                raw_state = payload.get("state", "off")
                state = raw_state if isinstance(raw_state, bool) else str(raw_state).lower() in ("1", "true", "on")
                self.actuators["DL"]["set_state"](1 if state else 0)
                self._publish_dl_state()
                log_line("DL", f"{'ON' if state else 'OFF'}")
            elif action == "db_activate" and "DB" in self.actuators:
                frequency = int(payload.get("frequency", 1000))
                duration = float(payload.get("duration", 1))
                threading.Thread(target=self._activate_db, args=(frequency, duration), daemon=True).start()
            elif action == "camera_start" and "CAMERA" in self.actuators:
                self.actuators["CAMERA"]["start"]()
                self._publish_camera_state()
            elif action == "camera_stop" and "CAMERA" in self.actuators:
                self.actuators["CAMERA"]["stop"]()
                self._publish_camera_state()
            elif action == "demo_pir":
                self._demo_pir(str(payload.get("sensor", "DPIR1")).strip().upper())
            elif action == "demo_ds":
                sensor = str(payload.get("sensor", "DS1")).strip().upper()
                state = 1 if str(payload.get("state", "1")).strip().lower() in ("1", "true", "on", "active") else 0
                self._demo_ds(sensor, state)
            elif action == "demo_gsg":
                self._demo_gsg()
            elif action == "demo_person":
                self._demo_person(str(payload.get("doorway", "1")), str(payload.get("direction", "enter")))
            else:
                log_line("COMMAND", f"Unsupported or unavailable action: {action}", "SYSTEM")
        except Exception as exc:
            log_line("COMMAND", f"Error handling {action}: {exc}", "SYSTEM")

    def _handle_brgb_button(self, button: str):
        if self.brgb_handler and button in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
            self.brgb_handler(button)
            self._publish_runtime_value("IR", button, self.settings.get("IR", {}).get("simulated", True))

    def _activate_db(self, frequency: int, duration: float):
        self.actuators["DB"]["activate"](frequency, duration)
        self._publish_runtime_value(
            "DB",
            {"frequency": frequency, "duration": duration, "activated": True},
            self.actuators["DB"].get("simulated", True),
        )
        log_line("DB", f"Activated {frequency}Hz for {duration}s")

    def _demo_pir(self, sensor: str):
        if self.alarm_controller and sensor in ("DPIR1", "DPIR2", "DPIR3"):
            self.alarm_controller.handle_pir(sensor)
            self._publish_runtime_value(sensor, 1, self.settings.get(sensor, {}).get("simulated", True))
            log_line(sensor, "Demo motion")

    def _demo_ds(self, sensor: str, state: int):
        if self.alarm_controller and sensor in ("DS1", "DS2"):
            self.alarm_controller.handle_ds(sensor, state)
            self._publish_runtime_value(sensor, state, self.settings.get(sensor, {}).get("simulated", True))
            log_line(sensor, f"Demo state {state}")

    def _demo_gsg(self):
        if self.alarm_controller:
            self.alarm_controller.handle_gsg(1)
            self._publish_runtime_value("GSG", 1, self.settings.get("GSG", {}).get("simulated", True))
            log_line("GSG", "Demo significant movement")

    def _demo_person(self, doorway: str, direction: str):
        pir = "DPIR1" if doorway == "1" else "DPIR2"
        dus = "DUS1" if doorway == "1" else "DUS2"
        if not self.alarm_controller:
            return

        entry_on_increasing = bool(
            self.settings.get("ALARM", {}).get(
                f"{pir.lower()}_entry_on_increasing",
                True if pir == "DPIR1" else False,
            )
        )
        entering = direction.strip().lower() == "enter"
        increasing = entering if entry_on_increasing else not entering
        values = [10, 20, 30, 40] if increasing else [40, 30, 20, 10]
        history = self.alarm_controller._dus_history.get(dus)
        if history is not None:
                history.clear()
        for value in values:
            self.alarm_controller.handle_dus(dus, value)
            self._publish_runtime_value(dus, value, self.settings.get(dus, {}).get("simulated", True))
        self.alarm_controller.handle_pir(pir)
        self._publish_runtime_value(pir, 1, self.settings.get(pir, {}).get("simulated", True))
        log_line(pir, f"Demo person {direction} via {dus}")

    def _start_sensors(self):
        if self.alarm_controller:
            self.alarm_controller.start(self.threads)

        def parse_pressed_released(message):
            text = str(message).lower()
            if "released" in text or "inactive" in text:
                return 0
            if "pressed" in text or "active" in text:
                return 1
            return None

        def parse_dms_button(message):
            text = str(message)
            if "Button pressed:" in text:
                return text.split("Button pressed:", 1)[1].strip()
            text = text.strip()
            return text[:1] if text else None

        if "DS1" in self.settings:
            def callback(message):
                self._log("DS1", message)
                if self.alarm_controller:
                    state = parse_pressed_released(message)
                    if state is not None:
                        self.alarm_controller.handle_ds("DS1", state)
            run_ds1(self.settings["DS1"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DS2" in self.settings:
            def callback(message):
                self._log("DS2", message)
                if self.alarm_controller:
                    state = parse_pressed_released(message)
                    if state is not None:
                        self.alarm_controller.handle_ds("DS2", state)
            run_ds2(self.settings["DS2"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DUS1" in self.settings:
            def callback(message):
                self._log("DUS1", message)
                if self.alarm_controller and isinstance(message, (int, float)):
                    self.alarm_controller.handle_dus("DUS1", message)
            run_dus1(self.settings["DUS1"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DUS2" in self.settings:
            def callback(message):
                self._log("DUS2", message)
                if self.alarm_controller and isinstance(message, (int, float)):
                    self.alarm_controller.handle_dus("DUS2", message)
            run_dus2(self.settings["DUS2"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DPIR1" in self.settings:
            def callback(message):
                self._log("DPIR1", message)
                if self.alarm_controller and "motion" in str(message).lower():
                    self.alarm_controller.handle_pir("DPIR1")
            run_dpir1(self.settings["DPIR1"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DPIR2" in self.settings:
            def callback(message):
                self._log("DPIR2", message)
                if self.alarm_controller and "motion" in str(message).lower():
                    self.alarm_controller.handle_pir("DPIR2")
            run_dpir2(self.settings["DPIR2"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DPIR3" in self.settings:
            def callback(message):
                self._log("DPIR3", message)
                if self.alarm_controller and "motion" in str(message).lower():
                    self.alarm_controller.handle_pir("DPIR3")
            run_dpir3(self.settings["DPIR3"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DMS" in self.settings:
            def callback(message):
                self._log("DMS", message)
                if self.alarm_controller:
                    key = parse_dms_button(message)
                    if key:
                        self.alarm_controller.handle_dms_key(key)
            run_dms(self.settings["DMS"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DHT1" in self.settings:
            def callback(humidity, temperature, code):
                self._log("DHT1", f"Humidity: {humidity}%, Temperature: {temperature}C, Code: {code}")
            run_dht1(self.settings["DHT1"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DHT2" in self.settings:
            def callback(humidity, temperature, code):
                self._log("DHT2", f"Humidity: {humidity}%, Temperature: {temperature}C, Code: {code}")
            run_dht2(self.settings["DHT2"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "DHT3" in self.settings:
            def callback(humidity, temperature, code):
                self._log("DHT3", f"Humidity: {humidity}%, Temperature: {temperature}C, Code: {code}")
            run_dht3(self.settings["DHT3"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "LCD" in self.settings:
            run_lcd(self.settings["LCD"], self.threads, self.stop_event, lambda msg: self._log("LCD", msg), self.mqtt_publisher, self.simulator_scheduler)

        if "4SD" in self.settings:
            self.actuators["4SD"] = run_4sd(
                self.settings["4SD"],
                self.threads,
                self.stop_event,
                lambda msg: self._log("4SD", msg),
                self.mqtt_publisher,
            )

        if "BTN" in self.settings:
            def btn_callback():
                if "4SD" in self.actuators and self.actuators["4SD"].get("button_press"):
                    self.actuators["4SD"]["button_press"]()
                    self._publish_runtime_value("BTN", 1, self.settings.get("BTN", {}).get("simulated", True))
                    self._log("BTN", "Pressed")
            run_btn(self.settings["BTN"], self.threads, self.stop_event, callback=btn_callback)

        if "GSG" in self.settings:
            def callback(value):
                self._log("GSG", f"{'Movement detected' if value == 1 else 'No movement'} ({value})")
                if self.alarm_controller:
                    self.alarm_controller.handle_gsg(value)
            run_gsg(self.settings["GSG"], self.threads, self.stop_event, callback, self.mqtt_publisher, self.simulator_scheduler)

        if "BRGB" in self.settings:
            self.brgb_handler = run_brgb(
                self.settings["BRGB"],
                self.threads,
                self.stop_event,
                lambda msg: self._log("BRGB", msg),
                self.mqtt_publisher,
            )

        if "IR" in self.settings:
            run_ir(
                self.settings["IR"],
                self.threads,
                self.stop_event,
                lambda button: self._log("IR", f"Button pressed: {button}"),
                self.mqtt_publisher,
                self.brgb_handler,
            )

    def _log(self, sensor_name: str, message):
        if not self.stop_event.is_set():
            log_line(sensor_name, str(message))


HeadlessSmartHome = SmartHomeRuntime


def _resolve_settings_path():
    settings_path = os.environ.get("SETTINGS_PATH", "")
    if settings_path and os.path.exists(settings_path):
        return settings_path
    if os.path.exists("settings.json"):
        return "settings.json"
    parent_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    if os.path.exists(parent_path):
        return parent_path
    return "settings.json"


def main():
    try:
        settings = load_settings(_resolve_settings_path())
    except FileNotFoundError:
        print("Error: settings.json not found", flush=True)
        sys.exit(1)
    except Exception as exc:
        print(f"Error loading settings: {exc}", flush=True)
        sys.exit(1)

    runtime = SmartHomeRuntime(settings)
    try:
        runtime.run_forever()
    except KeyboardInterrupt:
        print("", flush=True)
        log_line("SYSTEM", "Interrupted by user")
        runtime.shutdown()
    except Exception as exc:
        log_line("SYSTEM", f"Runtime error: {exc}")
        runtime.shutdown()
        raise


if __name__ == "__main__":
    main()
