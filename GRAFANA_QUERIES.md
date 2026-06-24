

### DS1 - Button/Door Sensor
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DS1")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

### DUS1 - Ultrasonic Distance Sensor
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DUS1")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

### DPIR1 - Motion/PIR Sensor
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DPIR1")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

### DMS - Keypad/Matrix Sensor

**Query to show button characters (for Table panel):**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DMS")
  |> filter(fn: (r) => r["_field"] == "value")
  |> keep(columns: ["_time", "button_pressed", "_value"])
  |> sort(columns: ["_time"], desc: true)
```

### DHT1 - Temperature and Humidity Sensor (Bedroom)

**Temperature:**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DHT1_TEMPERATURE")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

**Humidity:**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DHT1_HUMIDITY")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

### DHT2 - Temperature and Humidity Sensor (Master Bedroom)

**Temperature:**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DHT2_TEMPERATURE")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

**Humidity:**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DHT2_HUMIDITY")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

### DHT3 - Temperature and Humidity Sensor (Kitchen)

**Temperature:**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DHT3_TEMPERATURE")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

**Humidity:**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "DHT3_HUMIDITY")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

### GSG - Gyroscope Sensor (Motion Detection)

**Query for graph (shows movement events 0 or 1):**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "GSG")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: last, createEmpty: false)
```

**Query for events table (shows only movement events):**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "GSG")
  |> filter(fn: (r) => r["_field"] == "value")
  |> filter(fn: (r) => r["_value"] == 1.0)
  |> keep(columns: ["_time", "_value", "pi_id", "device_name"])
  |> sort(columns: ["_time"], desc: true)
```

### IR - Infrared Receiver

**Query for button presses (Table panel with button values):**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "IR")
  |> filter(fn: (r) => r["_field"] == "value")
  |> keep(columns: ["_time", "_value", "button_value", "pi_id", "device_name"])
  |> sort(columns: ["_time"], desc: true)
```

**Query for button presses graph (shows button numbers 0-9):**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "IR")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: last, createEmpty: false)
```

### BRGB - RGB LED Actuator

**Query for color changes (Table panel with color names):**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "BRGB")
  |> filter(fn: (r) => r["_field"] == "value")
  |> keep(columns: ["_time", "_value", "color_value", "pi_id", "device_name"])
  |> sort(columns: ["_time"], desc: true)
```

**Query for color changes timeline (Graph panel):**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "BRGB")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1m, fn: last, createEmpty: false)
```

### ALARM - State and Enter/Exit Events

**Query for ALARM state timeline (0/1):**
```flux
from(bucket: "NTP")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["sensor_type"] == "ALARM")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 10s, fn: last, createEmpty: false)
```

**Query for ALARM transitions (entered/exited):**
```flux
from(bucket: "NTP")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "alarm_events")
  |> filter(fn: (r) => r["_field"] == "alarm_state")
  |> keep(columns: ["_time", "_value", "event_type", "pi_id", "device_name"])
  |> sort(columns: ["_time"], desc: true)
```
