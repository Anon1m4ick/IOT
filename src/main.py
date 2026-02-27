import threading
import sys
import time
import os
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Input, RichLog, Static
from textual.binding import Binding
from settings import load_settings
from components.ds1 import run_ds1
from components.ds2 import run_ds2
from components.dus1 import run_dus1
from components.dus2 import run_dus2
from components.dpir1 import run_dpir1
from components.dpir2 import run_dpir2
from components.dpir3 import run_dpir3
from components.dms import run_dms
from components.dht1 import run_dht1
from components.dht2 import run_dht2
from components.dht3 import run_dht3
from components.lcd import run_lcd
from components.gsg import run_gsg
from components.ir import run_ir
from components.brgb import run_brgb
from components.dl import run_dl
from components.db import run_db
from components.foursd import run_4sd
from components.camera import run_camera
from components.btn import run_btn
from mqtt_publisher import MQTTPublisher
from alarm_controller import AlarmController

# Which Pi each sensor/actuator belongs to (for 3-panel routing)
SENSOR_TO_PI = {
    "DS1": "PI1", "DL": "PI1", "DUS1": "PI1", "DB": "PI1", "DPIR1": "PI1", "DMS": "PI1", "CAMERA": "PI1",
    "DS2": "PI2", "DUS2": "PI2", "DPIR2": "PI2", "4SD": "PI2", "BTN": "PI2", "DHT3": "PI2", "GSG": "PI2",
    "DHT1": "PI3", "DHT2": "PI3", "IR": "PI3", "BRGB": "PI3", "LCD": "PI3", "DPIR3": "PI3",
    "ALARM": "PI1", "SYSTEM": "PI1",
}
ACTUATOR_TO_PI = {
    "DL": "PI1", "DB": "PI1", "CAMERA": "PI1",
    "4SD": "PI2", "BTN": "PI2",
    "BRGB": "PI3", "LCD": "PI3",
    "ALARM": "PI1",
}


class SensorLog(RichLog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_lines = 200

    def add_sensor_data(self, sensor_name: str, message: str):
        t = time.localtime()
        timestamp = time.strftime('%H:%M:%S', t)
        colors = {
            'DS1': 'blue',
            'DS2': 'blue',
            'DUS1': 'cyan',
            'DUS2': 'cyan',
            'DPIR1': 'yellow',
            'DPIR2': 'yellow',
            'DPIR3': 'yellow',
            'DMS': 'magenta',
            'DHT1': 'red',
            'DHT2': 'red',
            'DHT3': 'red',
            'LCD': 'green',
            'GSG': 'white',
            'IR': 'magenta',
            'BRGB': 'cyan',
            '4SD': 'green',
            'CAMERA': 'cyan',
            'ALARM': 'red',
            'SYSTEM': 'green'
        }
        color = colors.get(sensor_name, 'white')
        self.write(f"[dim]{timestamp}[/dim] [{color}]{sensor_name:6}[/{color}] {message}")


class SmartHomeTUI(App):

    CSS_PATH = os.path.join(os.path.dirname(__file__), "app.tcss")

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, settings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = settings
        self.threads = []
        self.stop_event = threading.Event()
        self.actuators = {}
        self.sensor_log = None
        self.sensor_logs = {}  # PI1, PI2, PI3 -> SensorLog
        self.status_bar = None
        self.command_input = None
        self.mqtt_publisher = None
        self.brgb_handler = None  # Handler for BRGB control via IR commands
        self.alarm_controller = None

        self._init_actuators()
        self._init_mqtt_publisher()
        self._init_alarm_controller()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main-container"):
            with Horizontal(id="panels-row"):
                with Vertical(id="panel-pi1", classes="pi-panel"):
                    yield Static("PI1 — Door / Security", classes="panel-title")
                    yield SensorLog(id="sensor-log-pi1", markup=True, wrap=True, auto_scroll=True)
                with Vertical(id="panel-pi2", classes="pi-panel"):
                    yield Static("PI2 — Kitchen / Hall", classes="panel-title")
                    yield SensorLog(id="sensor-log-pi2", markup=True, wrap=True, auto_scroll=True)
                with Vertical(id="panel-pi3", classes="pi-panel"):
                    yield Static("PI3 — Bedroom / Living", classes="panel-title")
                    yield SensorLog(id="sensor-log-pi3", markup=True, wrap=True, auto_scroll=True)

            with Vertical(id="command-panel"):
                yield Static("Commands", classes="panel-title")
                yield Static(
                    "Use prefix: pi1 <cmd> | pi2 <cmd> | pi3 <cmd>  e.g. pi1 dl on, pi2 4sd start, pi3 ir 1",
                    classes="help-text"
                )
                yield Input(
                    placeholder="pi1 dl on | pi2 4sd start | pi3 ir 1 ...",
                    id="command-input"
                )
                yield Static("System ready. Type commands or 'help' for help.", id="status-bar")

        yield Footer()

    def on_mount(self) -> None:
        print("[Main] TUI mounted - application is running")
        self.sensor_log_pi1 = self.query_one("#sensor-log-pi1", SensorLog)
        self.sensor_log_pi2 = self.query_one("#sensor-log-pi2", SensorLog)
        self.sensor_log_pi3 = self.query_one("#sensor-log-pi3", SensorLog)
        self.sensor_logs = {"PI1": self.sensor_log_pi1, "PI2": self.sensor_log_pi2, "PI3": self.sensor_log_pi3}
        self.sensor_log = self.sensor_log_pi1  # fallback for any code that still uses it
        self.status_bar = self.query_one("#status-bar", Static)
        self.command_input = self.query_one("#command-input", Input)
        self.command_input.focus()

        self._start_sensors()
        self._update_status(f"System ready. Type commands or 'help' for help.")
        print("[Main] Sensors started, TUI is ready")

    def _init_actuators(self):
        if 'DL' in self.settings:
            self.actuators['DL'] = run_dl(self.settings['DL'])

        if 'DB' in self.settings:
            self.actuators['DB'] = run_db(self.settings['DB'])

        if 'CAMERA' in self.settings:
            self.actuators['CAMERA'] = run_camera(
                self.settings['CAMERA'],
                self.threads,
                self.stop_event,
                callback=lambda message: self._safe_log_from_thread("CAMERA", message),
            )

    def _init_alarm_controller(self):
        if 'ALARM' not in self.settings:
            return
        self.alarm_controller = AlarmController(
            self.settings['ALARM'],
            self.stop_event,
            self.actuators,
            mqtt_publisher=self.mqtt_publisher,
            event_callback=lambda msg: self._safe_log_from_thread("ALARM", msg),
            status_callback=lambda msg: self._update_status(f"ALARM: {msg}", from_thread=True),
        )
    
    def _init_mqtt_publisher(self):
        mqtt_config = self.settings.get('mqtt')
        device_config = self.settings.get('device', {})
        
        if mqtt_config:
            try:
                self.mqtt_publisher = MQTTPublisher(mqtt_config, device_config)
                self.mqtt_publisher.start()
                print("[Main] MQTT publisher initialized and started")
            except Exception as e:
                print(f"[Main] Warning: Failed to initialize MQTT publisher: {e}")
                self.mqtt_publisher = None
        else:
            print("[Main] MQTT configuration not found, MQTT publisher disabled")

    def _start_sensors(self):
        if self.alarm_controller:
            self.alarm_controller.start(self.threads)

        def create_callback(sensor_name):
            def callback(message):
                try:
                    if self.stop_event.is_set():
                        return
                    self._safe_log_from_thread(sensor_name, str(message))
                except (RuntimeError, AttributeError, Exception):
                    pass
            return callback

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

        if 'DS1' in self.settings:
            base_callback = create_callback("DS1")
            def callback(message, base_callback=base_callback):
                base_callback(message)
                if self.alarm_controller:
                    state = parse_pressed_released(message)
                    if state is not None:
                        self.alarm_controller.handle_ds("DS1", state)
            run_ds1(self.settings['DS1'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DUS1' in self.settings:
            base_callback = create_callback("DUS1")
            def callback(message, base_callback=base_callback):
                base_callback(message)
                if self.alarm_controller and isinstance(message, (int, float)):
                    self.alarm_controller.handle_dus("DUS1", message)
            run_dus1(self.settings['DUS1'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DPIR1' in self.settings:
            base_callback = create_callback("DPIR1")
            def callback(message, base_callback=base_callback):
                base_callback(message)
                if self.alarm_controller and "motion" in str(message).lower():
                    self.alarm_controller.handle_pir("DPIR1")
            run_dpir1(self.settings['DPIR1'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DMS' in self.settings:
            base_callback = create_callback("DMS")
            def callback(message, base_callback=base_callback):
                base_callback(message)
                if self.alarm_controller:
                    key = parse_dms_button(message)
                    if key:
                        self.alarm_controller.handle_dms_key(key)
            run_dms(self.settings['DMS'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DS2' in self.settings:
            base_callback = create_callback("DS2")
            def callback(message, base_callback=base_callback):
                base_callback(message)
                if self.alarm_controller:
                    state = parse_pressed_released(message)
                    if state is not None:
                        self.alarm_controller.handle_ds("DS2", state)
            run_ds2(self.settings['DS2'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DUS2' in self.settings:
            base_callback = create_callback("DUS2")
            def callback(message, base_callback=base_callback):
                base_callback(message)
                if self.alarm_controller and isinstance(message, (int, float)):
                    self.alarm_controller.handle_dus("DUS2", message)
            run_dus2(self.settings['DUS2'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DPIR2' in self.settings:
            base_callback = create_callback("DPIR2")
            def callback(message, base_callback=base_callback):
                base_callback(message)
                if self.alarm_controller and "motion" in str(message).lower():
                    self.alarm_controller.handle_pir("DPIR2")
            run_dpir2(self.settings['DPIR2'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DPIR3' in self.settings:
            base_callback = create_callback("DPIR3")
            def callback(message, base_callback=base_callback):
                base_callback(message)
                if self.alarm_controller and "motion" in str(message).lower():
                    self.alarm_controller.handle_pir("DPIR3")
            run_dpir3(self.settings['DPIR3'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if "DHT1" in self.settings:
            def dht1_callback(humidity, temperature, code):
                message = f"Humidity: {humidity}%, Temperature: {temperature}°C, Code: {code}"
                self._safe_log_from_thread("DHT1", message)
            run_dht1(self.settings["DHT1"], self.threads, self.stop_event, dht1_callback, self.mqtt_publisher)

        if "DHT2" in self.settings:
            def dht2_callback(humidity, temperature, code):
                message = f"Humidity: {humidity}%, Temperature: {temperature}°C, Code: {code}"
                self._safe_log_from_thread("DHT2", message)
            run_dht2(self.settings["DHT2"], self.threads, self.stop_event, dht2_callback, self.mqtt_publisher)

        if "DHT3" in self.settings:
            def dht3_callback(humidity, temperature, code):
                message = f"Humidity: {humidity}%, Temperature: {temperature}°C, Code: {code}"
                self._safe_log_from_thread("DHT3", message)
            run_dht3(self.settings["DHT3"], self.threads, self.stop_event, dht3_callback, self.mqtt_publisher)

        if "LCD" in self.settings:
            def lcd_callback(message):
                self._safe_log_from_thread("LCD", message)
            run_lcd(self.settings["LCD"], self.threads, self.stop_event, lcd_callback, self.mqtt_publisher)

        if '4SD' in self.settings:
            def foursd_callback(message):
                self._safe_log_from_thread("4SD", message)
            self.actuators['4SD'] = run_4sd(self.settings['4SD'], self.threads, self.stop_event, foursd_callback, self.mqtt_publisher)

        if 'BTN' in self.settings:
            def btn_callback():
                if '4SD' in self.actuators and self.actuators['4SD'].get('button_press'):
                    self.actuators['4SD']['button_press']()
            run_btn(self.settings['BTN'], self.threads, self.stop_event, callback=btn_callback)

        if "GSG" in self.settings:
            def gsg_callback(value):
                status = "Movement detected" if value == 1 else "No movement"
                message = f"{status} ({value})"
                self._safe_log_from_thread("GSG", message)
                if self.alarm_controller:
                    self.alarm_controller.handle_gsg(value)
            run_gsg(self.settings["GSG"], self.threads, self.stop_event, gsg_callback, self.mqtt_publisher)

        if "BRGB" in self.settings:
            def brgb_callback(message):
                self._safe_log_from_thread("BRGB", message)
            self.brgb_handler = run_brgb(self.settings["BRGB"], self.threads, self.stop_event, brgb_callback, self.mqtt_publisher)

        if "IR" in self.settings:
            def ir_callback(button):
                self._safe_log_from_thread("IR", f"Button pressed: {button}")
            run_ir(self.settings["IR"], self.threads, self.stop_event, ir_callback, self.mqtt_publisher, self.brgb_handler)

    def _update_status(self, message: str, from_thread: bool = False):
        if self.status_bar:
            if from_thread:
                self.call_from_thread(self.status_bar.update, message)
            else:
                self.status_bar.update(message)

    def _get_log_for_sensor(self, sensor_name: str):
        """Return the SensorLog widget for the Pi that owns this sensor/actor."""
        pi = SENSOR_TO_PI.get(sensor_name, "PI1")
        return self.sensor_logs.get(pi)

    def _safe_log_from_thread(self, sensor_name: str, message: str):
        try:
            if self.stop_event.is_set():
                return
            log = self._get_log_for_sensor(sensor_name)
            if log is None:
                return
            if threading.current_thread() is threading.main_thread():
                log.add_sensor_data(sensor_name, str(message))
            else:
                self.call_from_thread(log.add_sensor_data, sensor_name, str(message))
        except Exception:
            pass

    def _log_to_pi(self, pi: str, message: str, sensor_name: str = "SYSTEM"):
        """Write message to the log panel for the given Pi."""
        log = self.sensor_logs.get(pi) if pi else None
        if log is None:
            return
        if threading.current_thread() is threading.main_thread():
            log.add_sensor_data(sensor_name, message)
        else:
            self.call_from_thread(log.add_sensor_data, sensor_name, message)

    def _write_to_pi(self, pi: str, text: str):
        """Plain write (e.g. help text) to the given Pi's panel."""
        log = self.sensor_logs.get(pi) if pi else None
        if log is None:
            return
        log.write(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        event.input.value = ""

        if not command:
            return

        self._handle_command(command)

    def _handle_command(self, command: str):
        raw_parts = command.split()
        if not raw_parts:
            return

        target_pi = None
        if raw_parts[0].lower() in ("pi1", "pi2", "pi3"):
            target_pi = raw_parts[0].upper()
            parts = raw_parts[1:]
        else:
            parts = raw_parts

        if not parts:
            self._update_status("Usage: pi1 <cmd> | pi2 <cmd> | pi3 <cmd>")
            return

        cmd = parts[0].lower()

        if cmd == "quit" or cmd == "exit":
            self._update_status("Shutting down...")
            self.stop_event.set()
            self.exit()
            return

        elif cmd == "help":
            help_text = """
Use prefix pi1 | pi2 | pi3 before each command.
  pi1 dl on/off/status       - Door Light (PI1)
  pi1 db activate [freq][dur]- Buzzer (PI1)
  pi1 camera status|start|stop|url
  pi1 alarm status|arm|disarm|trigger [reason]
  pi1 dms pin <4 digits>     - Simulate DMS keypad PIN (e.g. pi1 dms pin 1234)
  pi2 4sd status|set <s>|start|stop|add [s]|btn|blink - Kitchen timer (PI2)
  pi3 ir <0-9>               - IR/BRGB (PI3): 0=OFF,1=WHITE,2=RED,3=GREEN,4=BLUE,5=YELLOW,6=PURPLE,7=LIGHT_BLUE,8=OFF,9=WHITE
  sensors | actuators        - Show status (no prefix)
  help | quit/exit           - No prefix
            """
            self._write_to_pi("PI1", help_text.strip())

        elif cmd == "dl":
            if target_pi != "PI1":
                self._update_status("DL is on PI1. Use: pi1 dl <on|off|status>")
                return
            if len(parts) < 2:
                self._update_status("Usage: pi1 dl <on|off|status>")
                return

            action = parts[1]
            if "DL" not in self.actuators:
                self._update_status("Error: Door Light (DL) not configured")
                return

            if action == "on":
                self.actuators["DL"]["set_state"](1)
                self._update_status("Door Light turned ON")
                self._log_to_pi("PI1", "Door Light turned ON")
            elif action == "off":
                self.actuators["DL"]["set_state"](0)
                self._update_status("Door Light turned OFF")
                self._log_to_pi("PI1", "Door Light turned OFF")
            elif action == "status":
                state = self.actuators["DL"]["get_state"]()
                status = "ON" if state else "OFF"
                self._update_status(f"Door Light status: {status}")
            else:
                self._update_status("Usage: pi1 dl <on|off|status>")

        elif cmd == "db":
            if target_pi != "PI1":
                self._update_status("DB is on PI1. Use: pi1 db activate [freq] [dur]")
                return
            if len(parts) < 2:
                self._update_status("Usage: pi1 db activate [frequency] [duration]")
                return

            action = parts[1]
            if "DB" not in self.actuators:
                self._update_status("Error: Door Buzzer (DB) not configured")
                return

            if action == "activate":
                try:
                    frequency = int(parts[2]) if len(parts) > 2 else 1000
                    duration = int(parts[3]) if len(parts) > 3 else 1
                except ValueError:
                    self._update_status("Error: Frequency and duration must be numbers")
                    return

                def buzzer_thread():
                    self.actuators["DB"]["activate"](frequency, duration)
                    self._log_to_pi("PI1", f"Buzzer stopped ({frequency}Hz, {duration}s)")

                thread = threading.Thread(target=buzzer_thread)
                thread.start()
                self._update_status(f"Buzzer activation started: {frequency}Hz for {duration}s")
                self._log_to_pi("PI1", f"Buzzer activated: {frequency}Hz for {duration}s")
            else:
                self._update_status("Usage: pi1 db activate [frequency] [duration]")

        elif cmd == "dms":
            if target_pi != "PI1":
                self._update_status("DMS is on PI1. Use: pi1 dms pin <4 digits>")
                return
            if not self.alarm_controller:
                self._update_status("Error: ALARM controller not configured")
                return
            if len(parts) < 3 or parts[1].lower() != "pin":
                self._update_status("Usage: pi1 dms pin <4 digits>  e.g. pi1 dms pin 1234")
                return
            pin_str = parts[2].strip()
            if not pin_str.isdigit() or len(pin_str) != 4:
                self._update_status("PIN must be exactly 4 digits")
                return
            for char in pin_str:
                self.alarm_controller.handle_dms_key(char)
            self._log_to_pi("PI1", f"DMS PIN entered via command: ****")
            self._update_status("DMS PIN entered (4 digits)")

        elif cmd == "ir":
            if target_pi != "PI3":
                self._update_status("IR/BRGB is on PI3. Use: pi3 ir <0-9>")
                return
            if len(parts) < 2:
                self._update_status("Usage: pi3 ir <0-9> (0=OFF,1=WHITE,2=RED,...)")
                return

            if not self.brgb_handler:
                self._update_status("Error: BRGB not configured")
                return

            try:
                button_number = parts[1]
                if button_number not in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                    self._update_status("Error: Button must be 0-9")
                    return

                self.brgb_handler(button_number)
                if self.mqtt_publisher:
                    self.mqtt_publisher.add_sensor_data("IR", button_number, self.settings.get("IR", {}).get("simulated", True))
                color_map = {
                    "0": "OFF", "1": "WHITE", "2": "RED", "3": "GREEN", "4": "BLUE",
                    "5": "YELLOW", "6": "PURPLE", "7": "LIGHT_BLUE", "8": "OFF", "9": "WHITE"
                }
                color = color_map.get(button_number, "UNKNOWN")
                self._update_status(f"IR button {button_number} pressed - BRGB: {color}")
                self._log_to_pi("PI3", f"IR command: button {button_number} -> {color}")
            except Exception as e:
                self._update_status(f"Error: {e}")

        elif cmd in ("4sd", "timer"):
            if target_pi != "PI2":
                self._update_status("4SD is on PI2. Use: pi2 4sd <status|set|start|stop|add|btn|blink>")
                return
            if "4SD" not in self.actuators:
                self._update_status("Error: 4SD timer/display not configured")
                return
            if len(parts) < 2:
                self._update_status("Usage: pi2 4sd status|set <s>|start|stop|add [s]|btn|blink")
                return

            action = parts[1]
            timer = self.actuators["4SD"]
            try:
                if action == "status":
                    state = timer["get_state"]()
                    self._log_to_pi("PI2", f"4SD state: {state}")
                    self._update_status(
                        f"4SD remaining={state['remaining_seconds']}s running={state['running']} blinking={state['expired_blinking']}"
                    )
                elif action == "set":
                    seconds = int(parts[2])
                    timer["set_duration"](seconds)
                    self._update_status(f"4SD timer set to {seconds}s")
                elif action == "start":
                    timer["start"]()
                    self._update_status("4SD timer started")
                elif action == "stop":
                    timer["stop"]()
                    self._update_status("4SD timer stopped")
                elif action == "add":
                    seconds = int(parts[2]) if len(parts) > 2 else None
                    timer["add_seconds"](seconds)
                    self._update_status("4SD timer updated")
                elif action == "btn":
                    timer["button_press"]()
                    self._update_status("4SD BTN press handled")
                elif action == "blink":
                    timer["trigger_expired_blink"]()
                    self._update_status("4SD blink test started")
                else:
                    self._update_status("Usage: pi2 4sd status|set <s>|start|stop|add [s]|btn|blink")
            except (ValueError, IndexError):
                self._update_status("Error: Invalid 4SD command arguments")
            except Exception as e:
                self._update_status(f"4SD error: {e}")

        elif cmd == "camera":
            if target_pi != "PI1":
                self._update_status("CAMERA is on PI1. Use: pi1 camera <status|start|stop|url>")
                return
            if "CAMERA" not in self.actuators:
                self._update_status("Error: CAMERA not configured")
                return
            if len(parts) < 2:
                self._update_status("Usage: pi1 camera status|start|stop|url")
                return

            action = parts[1]
            camera = self.actuators["CAMERA"]
            try:
                if action == "status":
                    state = camera["get_state"]()
                    self._log_to_pi("PI1", f"CAMERA state: {state}")
                    self._update_status(
                        f"CAMERA running={state['running']} simulated={state['simulated']} url={state['stream_url']}"
                    )
                elif action == "start":
                    camera["start"]()
                    state = camera["get_state"]()
                    self._update_status(f"CAMERA start requested (running={state['running']})")
                elif action == "stop":
                    camera["stop"]()
                    state = camera["get_state"]()
                    self._update_status(f"CAMERA stop requested (running={state['running']})")
                elif action == "url":
                    state = camera["get_state"]()
                    self._log_to_pi("PI1", f"CAMERA URL: {state['stream_url']}")
                    self._update_status(f"CAMERA URL: {state['stream_url']}")
                else:
                    self._update_status("Usage: pi1 camera status|start|stop|url")
            except Exception as e:
                self._update_status(f"CAMERA error: {e}")

        elif cmd == "alarm":
            if target_pi != "PI1":
                self._update_status("ALARM is on PI1. Use: pi1 alarm <status|arm|disarm|trigger [reason]>")
                return
            if not self.alarm_controller:
                self._update_status("Error: ALARM controller not configured")
                return
            if len(parts) < 2:
                self._update_status("Usage: pi1 alarm status|arm|disarm|trigger [reason]")
                return
            action = parts[1]
            if action == "status":
                state = self.alarm_controller.get_state()
                self._log_to_pi("PI1", f"ALARM state: {state}")
                self._update_status(
                    f"ALARM active={state['alarm_active']} armed={state['security_armed']} people={state['person_count']}"
                )
            elif action == "arm":
                self.alarm_controller.arm()
                self._update_status("Alarm arming started")
            elif action == "disarm":
                self.alarm_controller.disarm()
                self._update_status("Alarm disarmed")
            elif action == "trigger":
                reason = " ".join(parts[2:]) if len(parts) > 2 else "Manual console trigger"
                self.alarm_controller.trigger_alarm(reason)
                self._update_status("Alarm triggered")
            else:
                self._update_status("Usage: pi1 alarm status|arm|disarm|trigger [reason]")

        elif cmd == "sensors":
            info = "\nSensor Status:\n"
            sensors = ["DS1", "DS2", "DUS1", "DUS2", "DPIR1", "DPIR2", "DPIR3", "DMS", "DHT1", "DHT2", "DHT3", "GSG", "IR"]
            for sensor in sensors:
                pi = SENSOR_TO_PI.get(sensor, "?")
                if sensor in self.settings:
                    sim = "Simulated" if self.settings[sensor]["simulated"] else "Real"
                    info += f"  {sensor} ({pi}): {sim} - Running\n"
                else:
                    info += f"  {sensor} ({pi}): Not configured\n"
            self._write_to_pi("PI1", info.strip())

        elif cmd == "actuators":
            info = "\nActuator Status:\n"
            for actuator in ["DL", "DB", "4SD", "CAMERA"]:
                pi = ACTUATOR_TO_PI.get(actuator, "?")
                if actuator in self.actuators:
                    sim = "Simulated" if self.actuators[actuator].get("simulated", True) else "Real"
                    if actuator == "DL":
                        state = self.actuators[actuator]["get_state"]()
                        info += f"  {actuator} ({pi}): {sim} - Status: {'ON' if state else 'OFF'}\n"
                    elif actuator == "4SD":
                        state = self.actuators[actuator]["get_state"]()
                        info += f"  {actuator} ({pi}): {sim} - Remaining: {state['remaining_seconds']}s, Running: {state['running']}, Blinking: {state['expired_blinking']}\n"
                    elif actuator == "CAMERA":
                        state = self.actuators[actuator]["get_state"]()
                        info += f"  {actuator} ({pi}): {sim} - Running: {state['running']}, URL: {state['stream_url']}\n"
                    else:
                        info += f"  {actuator} ({pi}): {sim} - Ready\n"
                else:
                    info += f"  {actuator} ({pi}): Not configured\n"
            if self.alarm_controller:
                state = self.alarm_controller.get_state()
                info += f"  ALARM (PI1): {'Simulated' if state['simulated'] else 'Real'} - Active: {state['alarm_active']}, Armed: {state['security_armed']}, People: {state['person_count']}\n"
            self._write_to_pi("PI1", info.strip())

        else:
            if not target_pi:
                self._update_status(f"Use prefix: pi1 <cmd> | pi2 <cmd> | pi3 <cmd>. Unknown: {cmd}")
            else:
                self._update_status(f"Unknown command: {cmd}. Type help for list.")

    def action_quit(self) -> None:
        self._update_status("Shutting down...")
        self.stop_event.set()
        
        if self.mqtt_publisher:
            self.mqtt_publisher.stop()
        
        self.exit()

    def on_unmount(self) -> None:
        print("[Main] on_unmount called - application is closing")
        self.stop_event.set()
        
        if self.mqtt_publisher:
            self.mqtt_publisher.stop()
        
        for thread in self.threads:
            thread.join(timeout=2)


def main():
    settings_path = 'settings.json'
    if not os.path.exists(settings_path):
        parent_path = os.path.join(os.path.dirname(__file__), '..', 'settings.json')
        if os.path.exists(parent_path):
            settings_path = parent_path

    try:
        settings = load_settings(settings_path)
    except FileNotFoundError:
        print("Error: settings.json not found!")
        print("Please create a settings.json file with device configurations.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading settings: {e}")
        sys.exit(1)

    app = SmartHomeTUI(settings)
    
    try:
        print("[Main] Starting TUI application...")
        app.run()
    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user")
    except Exception as e:
        print(f"[Main] Error running TUI: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[Main] Application finished")


if __name__ == "__main__":
    main()
