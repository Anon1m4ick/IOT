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
from components.dus1 import run_dus1
from components.dpir1 import run_dpir1
from components.dms import run_dms
from components.dl import run_dl
from components.db import run_db


class SensorLog(RichLog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_lines = 200

    def add_sensor_data(self, sensor_name: str, message: str):
        t = time.localtime()
        timestamp = time.strftime('%H:%M:%S', t)
        colors = {
            'DS1': 'blue',
            'DUS1': 'cyan',
            'DPIR1': 'yellow',
            'DMS': 'magenta',
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

        self._init_actuators()

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
        self.sensor_log = self.query_one("#sensor-log", SensorLog)
        self.status_bar = self.query_one("#status-bar", Static)
        self.command_input = self.query_one("#command-input", Input)
        self.command_input.focus()

        self._start_sensors()
        self._update_status("System ready. Type commands or 'help' for help.")

    def _init_actuators(self):
        if 'DL' in self.settings:
            self.actuators['DL'] = run_dl(self.settings['DL'])

        if 'DB' in self.settings:
            self.actuators['DB'] = run_db(self.settings['DB'])

    def _start_sensors(self):
        def create_callback(sensor_name):
            def callback(message):
                self.call_from_thread(
                    self.sensor_log.add_sensor_data,
                    sensor_name,
                    str(message)
                )
            return callback

        if 'DS1' in self.settings:
            callback = create_callback("DS1")
            run_ds1(self.settings['DS1'], self.threads, self.stop_event, callback)

        if 'DUS1' in self.settings:
            callback = create_callback("DUS1")
            run_dus1(self.settings['DUS1'], self.threads, self.stop_event, callback)

        if 'DPIR1' in self.settings:
            callback = create_callback("DPIR1")
            run_dpir1(self.settings['DPIR1'], self.threads, self.stop_event, callback)

        if 'DMS' in self.settings:
            callback = create_callback("DMS")
            run_dms(self.settings['DMS'], self.threads, self.stop_event, callback)

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
            sensors = ['DS1', 'DUS1', 'DPIR1', 'DMS']
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
        self.exit()

    def on_unmount(self) -> None:
        self.stop_event.set()
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
    app.run()


if __name__ == "__main__":
    main()
