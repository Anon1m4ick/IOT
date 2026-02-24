# Hardware Setup

## Hardware Connections

### DMS (4x4 Keypad)

**Connections:**
- Rows: GPIO 25, 8, 7, 1
- Columns: GPIO 12, 16, 20, 21

**Key Layout:**
```
[1] [2] [3] [A]
[4] [5] [6] [B]
[7] [8] [9] [C]
[*] [0] [#] [D]
```

### DUS1 (Ultrasonic Sensor HC-SR04)

**Connections:**
- TRIG (trigger): GPIO 23
- ECHO (echo): GPIO 24
- VCC: 5V
- GND: GND

## Switching to Real Hardware

### 1. Install RPi.GPIO

On Raspberry Pi:
```bash
pip install RPi.GPIO
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure settings.json

Change `simulated: false` for the components you want to use:

```json
{
  "DMS": {
    "simulated": false,
    "rows": [25, 8, 7, 1],
    "cols": [12, 16, 20, 21]
  },
  "DUS1": {
    "simulated": false,
    "trig_pin": 23,
    "echo_pin": 24
  }
}
```

### 3. Run the System

Start the system as usual:
```bash
# Terminal 1: Server
python3 src/server.py

# Terminal 2: TUI Application
python3 src/main.py
```

## Important Notes

1. **Permissions**: GPIO access may require root privileges or adding the user to the `gpio` group:
   ```bash
   sudo usermod -a -G gpio $USER
   ```

2. **Testing**: Before running the full system, you can test individual components:
   ```bash
   # Test keypad
   python3 src/sensors/dms.py
   
   # Test ultrasonic sensor
   python3 src/sensors/dus1.py
   ```

3. **Mixed Mode**: You can use real hardware for some components and simulators for others by setting the appropriate `simulated` values in `settings.json`.

## Troubleshooting

### Error "RPi.GPIO is not available"
- Make sure the code is running on a Raspberry Pi
- Check installation: `pip list | grep RPi.GPIO`
- Install: `pip install RPi.GPIO`

### GPIO Pins Not Working
- Check the connections
- Make sure pins are not used by other processes
- Check GPIO access permissions

### Inaccurate Ultrasonic Sensor Readings
- Make sure the sensor is properly connected
- Check power supply (5V)
- Ensure there are no obstacles in front of the sensor
