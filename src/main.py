#!/usr/bin/env python3
import threading
import sys
import time
import os
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
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
from components.dl import run_dl
from components.db import run_db
from mqtt_publisher import MQTTPublisher


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
        self.status_bar = None
        self.command_input = None
        self.mqtt_publisher = None

        self._init_actuators()
        self._init_mqtt_publisher()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="main-container"):
            with Vertical(id="sensor-panel"):
                yield Static("Sensor Data Log", classes="panel-title")
                yield SensorLog(id="sensor-log", markup=True, wrap=True, auto_scroll=True)

            with Vertical(id="command-panel"):
                yield Static("Commands", classes="panel-title")
                yield Static(
                    "Commands: dl on/off/status | db activate [freq] [dur] | sensors | actuators | help",
                    classes="help-text"
                )
                yield Input(
                    placeholder="Enter command (e.g., 'dl on', 'db activate 1000 2')...",
                    id="command-input"
                )
                yield Static("System ready. Type commands or 'help' for help.", id="status-bar")

        yield Footer()

    def on_mount(self) -> None:
        print("[Main] TUI mounted - application is running")
        self.sensor_log = self.query_one("#sensor-log", SensorLog)
        self.status_bar = self.query_one("#status-bar", Static)
        self.command_input = self.query_one("#command-input", Input)
        self.command_input.focus()

        self._start_sensors()
        self._update_status("System ready. Type commands or 'help' for help.")
        print("[Main] Sensors started, TUI is ready")

    def _init_actuators(self):
        if 'DL' in self.settings:
            self.actuators['DL'] = run_dl(self.settings['DL'])

        if 'DB' in self.settings:
            self.actuators['DB'] = run_db(self.settings['DB'])
    
    def _init_mqtt_publisher(self):
        """Initialize MQTT publisher if MQTT config is available."""
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
        def create_callback(sensor_name):
            def callback(message):
                try:
                    if self.stop_event.is_set() or self.sensor_log is None:
                        return
                    self.call_from_thread(
                        self.sensor_log.add_sensor_data,
                        sensor_name,
                        str(message)
                    )
                except (RuntimeError, AttributeError, Exception):
                    pass
            return callback

        if 'DS1' in self.settings:
            callback = create_callback("DS1")
            run_ds1(self.settings['DS1'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DUS1' in self.settings:
            callback = create_callback("DUS1")
            run_dus1(self.settings['DUS1'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DPIR1' in self.settings:
            callback = create_callback("DPIR1")
            run_dpir1(self.settings['DPIR1'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DMS' in self.settings:
            callback = create_callback("DMS")
            run_dms(self.settings['DMS'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DS2' in self.settings:
            callback = create_callback("DS2")
            run_ds2(self.settings['DS2'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DUS2' in self.settings:
            callback = create_callback("DUS2")
            run_dus2(self.settings['DUS2'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DPIR2' in self.settings:
            callback = create_callback("DPIR2")
            run_dpir2(self.settings['DPIR2'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DPIR3' in self.settings:
            callback = create_callback("DPIR3")
            run_dpir3(self.settings['DPIR3'], self.threads, self.stop_event, callback, self.mqtt_publisher)

        if 'DHT1' in self.settings:
            def dht1_callback(humidity, temperature, code):
                message = f"Humidity: {humidity}%, Temperature: {temperature}°C, Code: {code}"
                self.call_from_thread(
                    self.sensor_log.add_sensor_data,
                    "DHT1",
                    message
                )
            run_dht1(self.settings['DHT1'], self.threads, self.stop_event, dht1_callback, self.mqtt_publisher)

        if 'DHT2' in self.settings:
            def dht2_callback(humidity, temperature, code):
                message = f"Humidity: {humidity}%, Temperature: {temperature}°C, Code: {code}"
                self.call_from_thread(
                    self.sensor_log.add_sensor_data,
                    "DHT2",
                    message
                )
            run_dht2(self.settings['DHT2'], self.threads, self.stop_event, dht2_callback, self.mqtt_publisher)

        if 'DHT3' in self.settings:
            def dht3_callback(humidity, temperature, code):
                message = f"Humidity: {humidity}%, Temperature: {temperature}°C, Code: {code}"
                self.call_from_thread(
                    self.sensor_log.add_sensor_data,
                    "DHT3",
                    message
                )
            run_dht3(self.settings['DHT3'], self.threads, self.stop_event, dht3_callback, self.mqtt_publisher)

        if 'LCD' in self.settings:
            def lcd_callback(message):
                self.call_from_thread(
                    self.sensor_log.add_sensor_data,
                    "LCD",
                    message
                )
            run_lcd(self.settings['LCD'], self.threads, self.stop_event, lcd_callback, self.mqtt_publisher)

    def _update_status(self, message: str, from_thread: bool = False):
        if self.status_bar:
            if from_thread:
                self.call_from_thread(self.status_bar.update, message)
            else:
                self.status_bar.update(message)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        event.input.value = ""

        if not command:
            return

        self._handle_command(command)

    def _handle_command(self, command: str):
        parts = command.lower().split()
        if not parts:
            return

        cmd = parts[0]

        if cmd == 'quit' or cmd == 'exit':
            self._update_status("Shutting down...")
            self.stop_event.set()
            self.exit()
            return

        elif cmd == 'help':
            help_text = """
Commands:
  dl on/off/status    - Control Door Light
  db activate [freq] [dur] - Activate Buzzer (default: 1000Hz, 1s)
  sensors             - Show sensor status
  actuators           - Show actuator status
  help                - Show this help
  quit/exit           - Exit application
            """
            self.sensor_log.write(help_text.strip())

        elif cmd == 'dl':
            if len(parts) < 2:
                self._update_status("Usage: dl <on|off|status>")
                return

            action = parts[1]
            if 'DL' not in self.actuators:
                self._update_status("Error: Door Light (DL) not configured")
                return

            if action == 'on':
                self.actuators['DL']['set_state'](1)
                self._update_status("Door Light turned ON")
                self.sensor_log.add_sensor_data("SYSTEM", "Door Light turned ON")
            elif action == 'off':
                self.actuators['DL']['set_state'](0)
                self._update_status("Door Light turned OFF")
                self.sensor_log.add_sensor_data("SYSTEM", "Door Light turned OFF")
            elif action == 'status':
                state = self.actuators['DL']['get_state']()
                status = "ON" if state else "OFF"
                self._update_status(f"Door Light status: {status}")
            else:
                self._update_status("Usage: dl <on|off|status>")

        elif cmd == 'db':
            if len(parts) < 2:
                self._update_status("Usage: db activate [frequency] [duration]")
                return

            action = parts[1]
            if 'DB' not in self.actuators:
                self._update_status("Error: Door Buzzer (DB) not configured")
                return

            if action == 'activate':
                try:
                    frequency = int(parts[2]) if len(parts) > 2 else 1000
                    duration = int(parts[3]) if len(parts) > 3 else 1
                except ValueError:
                    self._update_status("Error: Frequency and duration must be numbers")
                    return

                def buzzer_thread():
                    self.actuators['DB']['activate'](frequency, duration)
                    self.call_from_thread(
                        self.sensor_log.add_sensor_data,
                        "SYSTEM",
                        f"Buzzer stopped ({frequency}Hz, {duration}s)"
                    )

                thread = threading.Thread(target=buzzer_thread)
                thread.start()
                self._update_status(f"Buzzer activation started: {frequency}Hz for {duration}s")
                self.sensor_log.add_sensor_data("SYSTEM", f"Buzzer activated: {frequency}Hz for {duration}s")
            else:
                self._update_status("Usage: db activate [frequency] [duration]")

        elif cmd == 'sensors':
            info = "\nSensor Status:\n"
            sensors = ['DS1', 'DS2', 'DUS1', 'DUS2', 'DPIR1', 'DPIR2', 'DPIR3', 'DMS', 'DHT1', 'DHT2', 'DHT3']
            for sensor in sensors:
                if sensor in self.settings:
                    simulated = "Simulated" if self.settings[sensor]['simulated'] else "Real"
                    info += f"  {sensor}: {simulated} - Running\n"
                else:
                    info += f"  {sensor}: Not configured\n"
            self.sensor_log.write(info.strip())

        elif cmd == 'actuators':
            info = "\nActuator Status:\n"
            actuators = ['DL', 'DB']
            for actuator in actuators:
                if actuator in self.actuators:
                    simulated = "Simulated" if self.actuators[actuator]['simulated'] else "Real"
                    if actuator == 'DL':
                        state = self.actuators[actuator]['get_state']()
                        status = "ON" if state else "OFF"
                        info += f"  {actuator}: {simulated} - Status: {status}\n"
                    else:
                        info += f"  {actuator}: {simulated} - Ready\n"
                else:
                    info += f"  {actuator}: Not configured\n"
            self.sensor_log.write(info.strip())

        else:
            self._update_status(f"Unknown command: {cmd}. Type 'help' for available commands")

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
