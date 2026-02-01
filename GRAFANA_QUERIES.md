

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

