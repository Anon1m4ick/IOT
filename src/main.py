#!/usr/bin/env python3
import threading
import sys
import time
from settings import load_settings
from components.ds1 import run_ds1, ds1_callback
from components.dus1 import run_dus1, dus1_callback
from components.dpir1 import run_dpir1, dpir1_callback
from components.dms import run_dms, dms_callback
from components.dl import run_dl
from components.db import run_db


class SmartHomeCLI:
    def __init__(self, settings):
        self.settings = settings
        self.threads = []
        self.stop_event = threading.Event()
        self.actuators = {}
        self.running = True
        
        self._init_actuators()
        
        self._start_sensors()
    
    def _init_actuators(self):
        print("Initializing actuators...")
        
        if 'DL' in self.settings:
            self.actuators['DL'] = run_dl(self.settings['DL'])
            print(f"  DL (Door Light) initialized (simulated: {self.settings['DL']['simulated']})")
        
        if 'DB' in self.settings:
            self.actuators['DB'] = run_db(self.settings['DB'])
            print(f"  DB (Door Buzzer) initialized (simulated: {self.settings['DB']['simulated']})")
        
        print("Actuators initialized.\n")
    
    def _start_sensors(self):
        print("Starting sensors...")
        
        if 'DS1' in self.settings:
            run_ds1(self.settings['DS1'], self.threads, self.stop_event)
        
        if 'DUS1' in self.settings:
            run_dus1(self.settings['DUS1'], self.threads, self.stop_event)
        
        if 'DPIR1' in self.settings:
            run_dpir1(self.settings['DPIR1'], self.threads, self.stop_event)
        
        if 'DMS' in self.settings:
            run_dms(self.settings['DMS'], self.threads, self.stop_event)
        
        print("All sensors started. Sensor data will be displayed below.\n")
    
    def _print_menu(self):
        print("\n" + "="*50)
        print("Smart Home Control System - PI1")
        print("="*50)
        print("Commands:")
        print("  dl on          - Turn Door Light ON")
        print("  dl off         - Turn Door Light OFF")
        print("  dl status      - Check Door Light status")
        print("  db activate    - Activate Door Buzzer (default: 1000Hz, 1s)")
        print("  db activate <freq> <duration> - Activate buzzer with custom settings")
        print("  sensors        - Show sensor status")
        print("  actuators      - Show actuator status")
        print("  help           - Show this menu")
        print("  quit/exit      - Exit application")
        print("="*50)
        print()
    
    def _handle_command(self, command):
        parts = command.strip().lower().split()
        if not parts:
            return
        
        cmd = parts[0]
        
        if cmd == 'quit' or cmd == 'exit':
            print("Shutting down...")
            self.stop_event.set()
            self.running = False
            return
        
        elif cmd == 'help':
            self._print_menu()
        
        elif cmd == 'dl':
            if len(parts) < 2:
                print("Usage: dl <on|off|status>")
                return
            
            action = parts[1]
            if 'DL' not in self.actuators:
                print("Error: Door Light (DL) not configured")
                return
            
            if action == 'on':
                self.actuators['DL']['set_state'](1)
                print("✓ Door Light turned ON")
            elif action == 'off':
                self.actuators['DL']['set_state'](0)
                print("✓ Door Light turned OFF")
            elif action == 'status':
                state = self.actuators['DL']['get_state']()
                status = "ON" if state else "OFF"
                print(f"Door Light status: {status}")
            else:
                print("Usage: dl <on|off|status>")
        
        elif cmd == 'db':
            if len(parts) < 2:
                print("Usage: db activate [frequency] [duration]")
                return
            
            action = parts[1]
            if 'DB' not in self.actuators:
                print("Error: Door Buzzer (DB) not configured")
                return
            
            if action == 'activate':
                frequency = int(parts[2]) if len(parts) > 2 else 1000
                duration = int(parts[3]) if len(parts) > 3 else 1
                
                def buzzer_thread():
                    self.actuators['DB']['activate'](frequency, duration)
                
                thread = threading.Thread(target=buzzer_thread)
                thread.start()
                print(f"✓ Buzzer activation started: {frequency}Hz for {duration}s")
            else:
                print("Usage: db activate [frequency] [duration]")
        
        elif cmd == 'sensors':
            print("\nSensor Status:")
            print("-" * 30)
            sensors = ['DS1', 'DUS1', 'DPIR1', 'DMS']
            for sensor in sensors:
                if sensor in self.settings:
                    simulated = "Simulated" if self.settings[sensor]['simulated'] else "Real"
                    print(f"  {sensor}: {simulated} - Running")
                else:
                    print(f"  {sensor}: Not configured")
            print()
        
        elif cmd == 'actuators':
            print("\nActuator Status:")
            print("-" * 30)
            actuators = ['DL', 'DB']
            for actuator in actuators:
                if actuator in self.actuators:
                    simulated = "Simulated" if self.actuators[actuator]['simulated'] else "Real"
                    if actuator == 'DL':
                        state = self.actuators[actuator]['get_state']()
                        status = "ON" if state else "OFF"
                        print(f"  {actuator}: {simulated} - Status: {status}")
                    else:
                        print(f"  {actuator}: {simulated} - Ready")
                else:
                    print(f"  {actuator}: Not configured")
            print()
        
        else:
            print(f"Unknown command: {cmd}")
            print("Type 'help' for available commands")
    
    def run(self):
        self._print_menu()
        
        print("Sensor data will appear below. Type commands to control actuators.\n")
        print("-" * 50)
        
        try:
            while self.running:
                try:
                    command = input("PI1> ").strip()
                    if command:
                        self._handle_command(command)
                except EOFError:
                    print("\nShutting down...")
                    self.stop_event.set()
                    self.running = False
                except KeyboardInterrupt:
                    print("\n\nShutting down...")
                    self.stop_event.set()
                    self.running = False
        finally:
            print("Waiting for sensors to stop...")
            for thread in self.threads:
                thread.join(timeout=2)
            print("Application stopped.")


def main():
    import os
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
    
    print("="*50)
    print("Smart Home Control System - PI1")
    print("Initializing...")
    print("="*50)
    
    cli = SmartHomeCLI(settings)
    cli.run()


if __name__ == "__main__":
    main()
