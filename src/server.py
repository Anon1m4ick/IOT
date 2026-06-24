import json
import threading
import time
from datetime import datetime
from collections import deque
from typing import Dict, Any, Optional

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request, render_template, redirect, url_for
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


class MQTTInfluxDBBridge:
    
    def __init__(
        self,
        mqtt_config: Dict[str, Any],
        influxdb_config: Dict[str, Any],
        configured_simulated: Optional[Dict[str, bool]] = None,
    ):

        self.mqtt_config = mqtt_config
        self.influxdb_config = influxdb_config
        self.configured_simulated = configured_simulated or {}
        
        
        self.influx_client = None
        self.write_api = None
        
        
        self.mqtt_client = None
        self.connected = False
        self.subscribed = False 
        self.first_connect = True 
        
        # Lock for InfluxDB writes (minimal locking)
        self.influx_lock = threading.Lock()
        self.subscribe_lock = threading.Lock() 
        self.mqtt_lock = threading.Lock()

        self.control_topic = str(self.mqtt_config.get("control_topic", "commands/pi1"))
        self.extra_state_topics = {
            "ALARM_ARMED": "sensors/alarm_armed",
            "ALARM_ARMING": "sensors/alarm_arming",
            "ALARM_REASON": "sensors/alarm_reason",
            "DL": "sensors/dl",
            "DB": "sensors/db",
            "4SD_STATE": "sensors/4sd_state",
            "CAMERA_STATUS": "sensors/camera_status",
        }

        self.state_lock = threading.Lock()
        self.latest_sensor_values: Dict[str, Any] = {}
        self.latest_sensor_simulated: Dict[str, Optional[bool]] = {}
        self.notifications = deque(maxlen=200)
        self.state = {
            "alarm_active": False,
            "alarm_armed": False,
            "alarm_arming": False,
            "alarm_reason": "",
            "timer_remaining_seconds": 0,
            "timer_running": False,
            "timer_blinking": False,
            "timer_button_add_seconds": 0,
            "brgb_color": "OFF",
            "dl_state": None,
            "camera_status": {},
            "db_last": {},
            "person_count": 0,
            "updated_at": time.time(),
        }
        self._last_alarm_state: Optional[bool] = None
        
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when MQTT client connects."""
        code = getattr(rc, 'getReasonCode', lambda: rc)()
        if code == 0:
            self.connected = True
            
            if self.first_connect:
                print(f"[Server] Connected to MQTT broker")
                self.first_connect = False
            
            with self.subscribe_lock:
                if not self.subscribed:
                    # Subscribe to all sensor topics
                    topics = self.mqtt_config.get('topics', {})
                    for sensor_type, topic in topics.items():
                        client.subscribe(topic, qos=1)
                        print(f"[Server] Subscribed to {topic}")
                    configured_topics = set(topics.values())
                    for sensor_type, topic in self.extra_state_topics.items():
                        if topic not in configured_topics:
                            client.subscribe(topic, qos=1)
                            print(f"[Server] Subscribed to {topic}")
                    self.subscribed = True
        else:
            print(f"[Server] MQTT connection failed with code {code}")
            self.connected = False
    
    def _on_message(self, client, userdata, msg):

        try:
            print(f"[Server] Received message on topic: {msg.topic}")  # Отладочный принт
            payload = json.loads(msg.payload.decode('utf-8'))
            topic = msg.topic
            
            # Extract sensor type from topic
            sensor_type = topic.split('/')[-1].upper()
            
            print(f"[Server] Processing {sensor_type} data: value={payload.get('value')}, simulated={payload.get('simulated')}")
            
            # Store in InfluxDB
            self._store_in_influxdb(sensor_type, payload)
            self._update_runtime_state(sensor_type, payload)
            
        except json.JSONDecodeError as e:
            print(f"[Server] Error decoding JSON: {e}")
        except Exception as e:
            print(f"[Server] Error processing message: {e}")
    
    def _store_in_influxdb(self, sensor_type: str, data: Dict[str, Any]):

        if not self.write_api:
            return
        
        try:
            # Create InfluxDB point
            point = Point("sensor_data") \
                .tag("sensor_type", sensor_type) \
                .tag("pi_id", data.get('pi_id', 'unknown')) \
                .tag("device_name", data.get('device_name', 'unknown')) \
                .tag("simulated", str(data.get('simulated', False)))
            
            # Special handling for DMS (keypad) - store button character as tag
            raw_value = data.get('value')
            if sensor_type == "DMS":
                # Store the actual button character as a tag
                button_char = str(raw_value).strip()
                point = point.tag("button_pressed", button_char)
                # Also store numeric value for graphing (mapping: 0-9 = 0-9, A=10, B=11, C=12, D=13, *=14, #=15)
                numeric_value = self._convert_dms_value(button_char)
                point = point.field("value", numeric_value)
            elif sensor_type == "IR":
                # For IR, store string value as tag and numeric mapping as field
                string_value = str(raw_value).strip()
                point = point.tag("button_value", string_value)
                # IR: button numbers 0-9 map to 0-9
                numeric_value = float(string_value) if string_value.isdigit() else 0.0
                point = point.field("value", numeric_value)
            elif sensor_type == "BRGB":
                # For BRGB, store string value as tag and use hash for graphing (to maintain old graph appearance)
                string_value = str(raw_value).strip()
                point = point.tag("color_value", string_value)
                # Use hash to get values in 2k-10k range (like before)
                numeric_value = float(hash(string_value) % 10000)
                point = point.field("value", numeric_value)
            else:
                # For other sensors, use standard conversion
                point = point.field("value", self._convert_value(raw_value))
            
            point = point.time(int(data.get('timestamp', time.time()) * 1e9), WritePrecision.NS)
            
            # Minimal locking - only during write
            with self.influx_lock:
                self.write_api.write(
                    bucket=self.influxdb_config['bucket'],
                    org=self.influxdb_config['org'],
                    record=point
                )
            
            print(f"[Server] Stored {sensor_type} data: {data.get('value')}")
            
        except Exception as e:
            print(f"[Server] Error storing in InfluxDB: {e}")

    def _store_alarm_transition_event(self, active: bool, data: Dict[str, Any]):
        if not self.write_api:
            return
        try:
            event_type = "entered" if active else "exited"
            point = Point("alarm_events") \
                .tag("event_type", event_type) \
                .tag("pi_id", data.get("pi_id", "unknown")) \
                .tag("device_name", data.get("device_name", "unknown")) \
                .tag("simulated", str(data.get("simulated", False))) \
                .field("alarm_state", 1 if active else 0) \
                .time(int(data.get("timestamp", time.time()) * 1e9), WritePrecision.NS)
            with self.influx_lock:
                self.write_api.write(
                    bucket=self.influxdb_config['bucket'],
                    org=self.influxdb_config['org'],
                    record=point
                )
        except Exception as e:
            print(f"[Server] Error storing alarm transition event: {e}")

    def _add_notification(self, message: str, level: str = "info"):
        now = datetime.now().strftime("%H:%M:%S")
        item = {
            "timestamp": now,
            "message": str(message),
            "level": str(level),
        }
        with self.state_lock:
            self.notifications.appendleft(item)

    def _update_runtime_state(self, sensor_type: str, data: Dict[str, Any]):
        value = data.get("value")
        timestamp = float(data.get("timestamp", time.time()))

        with self.state_lock:
            self.latest_sensor_values[sensor_type] = value
            self.latest_sensor_simulated[sensor_type] = data.get("simulated")
            self.state["updated_at"] = timestamp

            if sensor_type == "4SD":
                try:
                    self.state["timer_remaining_seconds"] = max(0, int(float(value)))
                except Exception:
                    pass
            elif sensor_type == "BRGB":
                self.state["brgb_color"] = str(value).upper()
            elif sensor_type == "DL":
                try:
                    self.state["dl_state"] = bool(int(float(value)))
                except Exception:
                    pass
            elif sensor_type == "DB":
                self.state["db_last"] = value if isinstance(value, dict) else {"value": value}
            elif sensor_type == "4SD_STATE" and isinstance(value, dict):
                self.state["timer_remaining_seconds"] = int(value.get("remaining_seconds", self.state["timer_remaining_seconds"]))
                self.state["timer_running"] = bool(value.get("running", False))
                self.state["timer_blinking"] = bool(value.get("expired_blinking", False))
                self.state["timer_button_add_seconds"] = int(value.get("button_add_seconds", 0))
            elif sensor_type == "CAMERA_STATUS" and isinstance(value, dict):
                self.state["camera_status"] = value
            elif sensor_type == "ALARM_ARMED":
                self.state["alarm_armed"] = bool(int(float(value)))
            elif sensor_type == "ALARM_ARMING":
                self.state["alarm_arming"] = bool(int(float(value)))
            elif sensor_type == "ALARM_REASON":
                self.state["alarm_reason"] = str(value)
            elif sensor_type == "ALARM_PEOPLE":
                try:
                    self.state["person_count"] = max(0, int(float(value)))
                except Exception:
                    pass

        if sensor_type == "ALARM":
            active = bool(int(float(value))) if value is not None else False
            should_store_transition = False
            with self.state_lock:
                self.state["alarm_active"] = active
                if self._last_alarm_state is None or self._last_alarm_state != active:
                    should_store_transition = True
                    self._last_alarm_state = active
            if should_store_transition:
                self._store_alarm_transition_event(active, data)
                self._add_notification(
                    "ALARM ACTIVATED" if active else "ALARM DEACTIVATED",
                    level="critical" if active else "success",
                )
        elif sensor_type in ("DPIR1", "DPIR2", "DPIR3"):
            try:
                if int(float(value)) == 1:
                    self._add_notification(f"{sensor_type}: motion detected", level="warning")
            except Exception:
                pass
        elif sensor_type == "GSG":
            try:
                if int(float(value)) == 1:
                    self._add_notification("GSG significant movement detected", level="warning")
            except Exception:
                pass
        elif sensor_type == "DMS":
            self._add_notification(f"DMS key: {value}", level="info")

    def get_dashboard_state(self) -> Dict[str, Any]:
        with self.state_lock:
            latest = dict(self.latest_sensor_values)
            simulated = dict(self.latest_sensor_simulated)
            notifications = list(self.notifications)[:50]
            state_snapshot = dict(self.state)

        dht = {}
        for idx in ("1", "2", "3"):
            temp_key = f"DHT{idx}_TEMPERATURE"
            hum_key = f"DHT{idx}_HUMIDITY"
            dht[f"DHT{idx}"] = {
                "temperature": latest.get(temp_key),
                "humidity": latest.get(hum_key),
            }

        system_elements = [
            {"code": "DS1", "name": "Door sensor 1", "pi": "PI1", "kind": "sensor", "value": latest.get("DS1"), "simulated": self._simulated_flag(simulated, "DS1")},
            {"code": "DUS1", "name": "Door ultrasonic 1", "pi": "PI1", "kind": "sensor", "value": latest.get("DUS1"), "simulated": self._simulated_flag(simulated, "DUS1")},
            {"code": "DPIR1", "name": "Door motion 1", "pi": "PI1", "kind": "sensor", "value": latest.get("DPIR1"), "simulated": self._simulated_flag(simulated, "DPIR1")},
            {"code": "DMS", "name": "Membrane switch", "pi": "PI1", "kind": "sensor", "value": latest.get("DMS"), "simulated": self._simulated_flag(simulated, "DMS")},
            {"code": "DL", "name": "Door light", "pi": "PI1", "kind": "actuator", "value": state_snapshot.get("dl_state"), "simulated": self._simulated_flag(simulated, "DL")},
            {"code": "DB", "name": "Door buzzer", "pi": "PI1", "kind": "actuator", "value": state_snapshot.get("db_last"), "simulated": self._simulated_flag(simulated, "DB")},
            {"code": "WEBC", "name": "Web camera", "pi": "PI1", "kind": "actuator", "value": state_snapshot.get("camera_status"), "simulated": self._simulated_flag(simulated, "CAMERA_STATUS", "CAMERA")},
            {"code": "DS2", "name": "Door sensor 2", "pi": "PI2", "kind": "sensor", "value": latest.get("DS2"), "simulated": self._simulated_flag(simulated, "DS2")},
            {"code": "DUS2", "name": "Door ultrasonic 2", "pi": "PI2", "kind": "sensor", "value": latest.get("DUS2"), "simulated": self._simulated_flag(simulated, "DUS2")},
            {"code": "DPIR2", "name": "Door motion 2", "pi": "PI2", "kind": "sensor", "value": latest.get("DPIR2"), "simulated": self._simulated_flag(simulated, "DPIR2")},
            {"code": "4SD", "name": "Kitchen stopwatch", "pi": "PI2", "kind": "actuator", "value": latest.get("4SD_STATE", latest.get("4SD")), "simulated": self._simulated_flag(simulated, "4SD_STATE", "4SD")},
            {"code": "BTN", "name": "Kitchen button", "pi": "PI2", "kind": "sensor", "value": latest.get("BTN"), "simulated": self._simulated_flag(simulated, "BTN")},
            {"code": "DHT3", "name": "Kitchen DHT", "pi": "PI2", "kind": "sensor", "value": dht.get("DHT3"), "simulated": self._simulated_flag(simulated, "DHT3_TEMPERATURE", "DHT3_HUMIDITY", "DHT3")},
            {"code": "GSG", "name": "Gyroscope", "pi": "PI2", "kind": "sensor", "value": latest.get("GSG"), "simulated": self._simulated_flag(simulated, "GSG")},
            {"code": "DHT1", "name": "Bedroom DHT", "pi": "PI3", "kind": "sensor", "value": dht.get("DHT1"), "simulated": self._simulated_flag(simulated, "DHT1_TEMPERATURE", "DHT1_HUMIDITY", "DHT1")},
            {"code": "DHT2", "name": "Master bedroom DHT", "pi": "PI3", "kind": "sensor", "value": dht.get("DHT2"), "simulated": self._simulated_flag(simulated, "DHT2_TEMPERATURE", "DHT2_HUMIDITY", "DHT2")},
            {"code": "IR", "name": "Bedroom infrared", "pi": "PI3", "kind": "sensor", "value": latest.get("IR"), "simulated": self._simulated_flag(simulated, "IR")},
            {"code": "BRGB", "name": "Bedroom RGB", "pi": "PI3", "kind": "actuator", "value": state_snapshot.get("brgb_color"), "simulated": self._simulated_flag(simulated, "BRGB")},
            {"code": "LCD", "name": "Living room LCD", "pi": "PI3", "kind": "actuator", "value": dht, "simulated": self._simulated_flag(simulated, "LCD")},
            {"code": "DPIR3", "name": "Living room motion", "pi": "PI3", "kind": "sensor", "value": latest.get("DPIR3"), "simulated": self._simulated_flag(simulated, "DPIR3")},
            {"code": "ALARM", "name": "Security alarm", "pi": "PI1", "kind": "logic", "value": {
                "active": state_snapshot.get("alarm_active"),
                "armed": state_snapshot.get("alarm_armed"),
                "arming": state_snapshot.get("alarm_arming"),
                "reason": state_snapshot.get("alarm_reason"),
            }, "simulated": self._simulated_flag(simulated, "ALARM")},
        ]

        return {
            "state": state_snapshot,
            "latest_sensors": latest,
            "latest_simulated": simulated,
            "dht": dht,
            "system_elements": system_elements,
            "notifications": notifications,
            "control_topic": self.control_topic,
        }

    def _simulated_flag(self, latest_simulated: Dict[str, Any], *keys: str) -> Optional[bool]:
        for key in keys:
            if latest_simulated.get(key) is not None:
                return bool(latest_simulated[key])
        for key in keys:
            if key in self.configured_simulated:
                return bool(self.configured_simulated[key])
        return None

    def publish_command(self, action: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        if not self.mqtt_client or not self.connected:
            print("[Server] MQTT is not connected; attempting reconnect before publishing command")
            self.connect_mqtt()
        if not self.mqtt_client or not self.connected:
            return False
        command = {
            "action": str(action).strip().lower(),
            "payload": payload or {},
            "source": "web",
            "timestamp": time.time(),
        }
        try:
            with self.mqtt_lock:
                result = self.mqtt_client.publish(self.control_topic, json.dumps(command), qos=1)
            ok = result.rc == mqtt.MQTT_ERR_SUCCESS
            if ok:
                self._add_notification(f"Command sent: {command['action']}", level="info")
            return ok
        except Exception as e:
            print(f"[Server] Error publishing command: {e}")
            return False
    
    def _convert_value(self, value: Any) -> float:

        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            # Try to convert string to number
            try:
                return float(value)
            except ValueError:
                # For non-numeric strings (like button presses
                return float(hash(value) % 10000)
        else:
            return 0.0
    
    def _convert_dms_value(self, button_char: str) -> float:

        button_char = str(button_char).strip().upper()
        
        # Numeric buttons
        if button_char.isdigit():
            return float(button_char)
        
        # Letter buttons
        button_map = {
            'A': 10,
            'B': 11,
            'C': 12,
            'D': 13,
            '*': 14,
            '#': 15
        }
        
        return float(button_map.get(button_char, 0))
    
    def connect_mqtt(self):

        if self.mqtt_client and self.connected:
            print("[Server] Already connected to MQTT broker")
            return

        if self.mqtt_client and not self.connected:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception:
                pass
            self.mqtt_client = None
        
        try:
            server_client_id = self.mqtt_config.get('server_client_id', 'iot_server')
            self.mqtt_client = mqtt.Client(
                client_id=server_client_id,
                protocol=mqtt.MQTTv5,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_message = self._on_message
            
            broker_host = self.mqtt_config.get('broker_host', 'localhost')
            broker_port = self.mqtt_config.get('broker_port', 1883)
            
            self.mqtt_client.connect(broker_host, broker_port, keepalive=60)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            time.sleep(1)
            
        except Exception as e:
            print(f"[Server] Error connecting to MQTT: {e}")
    
    def connect_influxdb(self):

        try:
            self.influx_client = InfluxDBClient(
                url=self.influxdb_config['url'],
                token=self.influxdb_config['token'],
                org=self.influxdb_config['org']
            )
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
            print(f"[Server] Connected to InfluxDB at {self.influxdb_config['url']}")
        except Exception as e:
            print(f"[Server] Error connecting to InfluxDB: {e}")
    
    def disconnect(self):
        """Disconnect from MQTT and InfluxDB."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            self.connected = False
            self.first_connect = True 
            with self.subscribe_lock:
                self.subscribed = False
        
        if self.write_api:
            self.write_api.close()
        
        if self.influx_client:
            self.influx_client.close()


# Flask app
app = Flask(__name__)
bridge: Optional[MQTTInfluxDBBridge] = None


def _get_camera_config() -> Dict[str, Any]:
    return app.config.get("camera_config", {})


def _camera_enabled() -> bool:
    return bool(_get_camera_config())


def _camera_stream_url() -> str:
    cfg = _get_camera_config()
    port = int(cfg.get("port", 8080))
    return str(cfg.get("stream_url", f"http://localhost:{port}/?action=stream"))


def _configured_simulated(settings: Dict[str, Any]) -> Dict[str, bool]:
    return {
        name: bool(config["simulated"])
        for name, config in settings.items()
        if isinstance(config, dict) and "simulated" in config
    }


@app.route('/health', methods=['GET'])
def health():

    return jsonify({
        'status': 'ok',
        'mqtt_connected': bridge.connected if bridge else False,
        'influxdb_connected': bridge.write_api is not None if bridge else False,
        'camera_enabled': _camera_enabled(),
    })


@app.route('/api/sensors', methods=['GET'])
def get_sensors():

    return jsonify({
        'sensors': [
            'DS1', 'DS2', 'DUS1', 'DUS2', 'DPIR1', 'DPIR2', 'DPIR3', 'DMS',
            'DHT1', 'DHT2', 'DHT3', 'GSG', 'IR'
        ],
        'actuators': ['DL', 'DB', '4SD', 'BRGB', 'LCD', 'CAMERA', 'ALARM']
    })


@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_snapshot():
    if not bridge:
        return jsonify({'status': 'error', 'message': 'bridge is not initialized'}), 503
    return jsonify({'status': 'ok', **bridge.get_dashboard_state()})


@app.route('/api/command', methods=['POST'])
def send_dashboard_command():
    data = request.get_json(silent=True) or {}
    action = str(data.get("action", "")).strip().lower()
    payload = data.get("payload", {})

    if not action:
        return jsonify({'status': 'error', 'message': 'action is required'}), 400
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return jsonify({'status': 'error', 'message': 'payload must be an object'}), 400

    ok = _publish_dashboard_command(action, payload)
    return jsonify({
        'status': 'success' if ok else 'mqtt_error',
        'action': action,
    }), 200 if ok else 503


@app.route('/api/actuators/dl', methods=['POST'])
def control_door_light():

    data = request.get_json() or {}
    state = str(data.get('state', 'off')).strip().lower()
    if state not in {"on", "off"}:
        return jsonify({'status': 'error', 'message': 'state must be on or off'}), 400
    ok = _publish_dashboard_command("dl_set", {"state": state})
    
    return jsonify({
        'status': 'success' if ok else 'mqtt_error',
        'actuator': 'DL',
        'state': state,
        'message': f'Door light command sent: {state}'
    }), 200 if ok else 503


@app.route('/api/actuators/db', methods=['POST'])
def control_door_buzzer():

    data = request.get_json() or {}
    try:
        frequency = int(data.get('frequency', 1000))
        duration = float(data.get('duration', 1))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'frequency and duration must be numbers'}), 400
    ok = _publish_dashboard_command("db_activate", {"frequency": frequency, "duration": duration})
    
    return jsonify({
        'status': 'success' if ok else 'mqtt_error',
        'actuator': 'DB',
        'frequency': frequency,
        'duration': duration,
        'message': f'Buzzer command sent: {frequency}Hz for {duration}s'
    }), 200 if ok else 503


@app.route('/api/camera', methods=['GET'])
def get_camera_info():
    if not _camera_enabled():
        return jsonify({
            'status': 'error',
            'message': 'CAMERA is not configured'
        }), 404
    cfg = _get_camera_config()
    return jsonify({
        'status': 'ok',
        'simulated': bool(cfg.get('simulated', False)),
        'auto_start': bool(cfg.get('auto_start', False)),
        'port': int(cfg.get('port', 8080)),
        'stream_url': _camera_stream_url(),
    })


@app.route('/camera', methods=['GET'])
def camera_page():
    if not _camera_enabled():
        return (
            "<h1>CAMERA not configured</h1><p>Add CAMERA section in settings.json.</p>",
            404,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    return render_template("camera.html", stream_url=_camera_stream_url())


@app.route('/dashboard', methods=['GET'])
def dashboard_page():
    snapshot = bridge.get_dashboard_state() if bridge else {
        "state": {
            "alarm_active": False,
            "alarm_armed": False,
            "alarm_arming": False,
            "alarm_reason": "",
            "timer_remaining_seconds": 0,
            "timer_running": False,
            "timer_blinking": False,
            "timer_button_add_seconds": 0,
            "brgb_color": "OFF",
            "dl_state": None,
            "camera_status": {},
            "db_last": {},
            "person_count": 0,
            "updated_at": time.time(),
        },
        "latest_sensors": {},
        "dht": {},
        "system_elements": [],
        "notifications": [],
    }
    status = request.args.get("status", "")
    return render_template(
        "dashboard.html",
        state=snapshot.get("state", {}),
        latest_sensors=snapshot.get("latest_sensors", {}),
        dht=snapshot.get("dht", {}),
        system_elements=snapshot.get("system_elements", []),
        notifications=snapshot.get("notifications", []),
        control_topic=snapshot.get("control_topic", ""),
        camera_enabled=_camera_enabled(),
        camera_stream_url=_camera_stream_url() if _camera_enabled() else "",
        camera_page_url=url_for("camera_page"),
        grafana_url=app.config.get("grafana_url", "http://localhost:3000"),
        status=status,
    )


def _publish_dashboard_command(action: str, payload: Optional[Dict[str, Any]] = None) -> bool:
    if not bridge:
        return False
    return bridge.publish_command(action, payload or {})


@app.route('/dashboard/alarm/arm', methods=['POST'])
def dashboard_alarm_arm():
    ok = _publish_dashboard_command("alarm_arm")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/alarm/disarm', methods=['POST'])
def dashboard_alarm_disarm():
    ok = _publish_dashboard_command("alarm_disarm")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/alarm/trigger', methods=['POST'])
def dashboard_alarm_trigger():
    reason = str(request.form.get("reason", "Web manual trigger")).strip() or "Web manual trigger"
    ok = _publish_dashboard_command("alarm_trigger", {"reason": reason})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/alarm/pin', methods=['POST'])
def dashboard_alarm_pin():
    pin = str(request.form.get("pin", "")).strip()
    if not (pin.isdigit() and len(pin) == 4):
        return redirect(url_for("dashboard_page", status="invalid_pin"))
    ok = _publish_dashboard_command("alarm_pin", {"pin": pin})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/timer/set', methods=['POST'])
def dashboard_timer_set():
    try:
        seconds = int(request.form.get("seconds", "0"))
    except ValueError:
        return redirect(url_for("dashboard_page", status="invalid_seconds"))
    ok = _publish_dashboard_command("timer_set", {"seconds": max(0, seconds)})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/timer/start', methods=['POST'])
def dashboard_timer_start():
    ok = _publish_dashboard_command("timer_start")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/timer/stop', methods=['POST'])
def dashboard_timer_stop():
    ok = _publish_dashboard_command("timer_stop")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/timer/add', methods=['POST'])
def dashboard_timer_add():
    raw = str(request.form.get("seconds", "")).strip()
    payload = {}
    if raw:
        try:
            payload["seconds"] = max(0, int(raw))
        except ValueError:
            return redirect(url_for("dashboard_page", status="invalid_seconds"))
    ok = _publish_dashboard_command("timer_add", payload)
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/timer/button', methods=['POST'])
def dashboard_timer_button():
    ok = _publish_dashboard_command("timer_button")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/timer/blink', methods=['POST'])
def dashboard_timer_blink():
    ok = _publish_dashboard_command("timer_blink")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/timer/button_add', methods=['POST'])
def dashboard_timer_button_add():
    try:
        seconds = int(request.form.get("seconds", "0"))
    except ValueError:
        return redirect(url_for("dashboard_page", status="invalid_seconds"))
    ok = _publish_dashboard_command("timer_set_button_add", {"seconds": max(0, seconds)})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/brgb', methods=['POST'])
def dashboard_brgb():
    button = str(request.form.get("button", "")).strip()
    if button not in {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}:
        return redirect(url_for("dashboard_page", status="invalid_brgb"))
    ok = _publish_dashboard_command("brgb_button", {"button": button})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/brgb/color', methods=['POST'])
def dashboard_brgb_color():
    color = str(request.form.get("color", "")).strip().upper()
    allowed = {"OFF", "WHITE", "RED", "GREEN", "BLUE", "YELLOW", "PURPLE", "LIGHT_BLUE"}
    if color not in allowed:
        return redirect(url_for("dashboard_page", status="invalid_brgb"))
    ok = _publish_dashboard_command("brgb_color", {"color": color})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/dl', methods=['POST'])
def dashboard_dl():
    state = str(request.form.get("state", "off")).strip().lower()
    if state not in {"on", "off"}:
        return redirect(url_for("dashboard_page", status="invalid_dl"))
    ok = _publish_dashboard_command("dl_set", {"state": state})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/db', methods=['POST'])
def dashboard_db():
    try:
        frequency = int(request.form.get("frequency", "1000"))
        duration = float(request.form.get("duration", "1"))
    except ValueError:
        return redirect(url_for("dashboard_page", status="invalid_db"))
    ok = _publish_dashboard_command("db_activate", {
        "frequency": max(1, frequency),
        "duration": max(0.1, duration),
    })
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/camera/start', methods=['POST'])
def dashboard_camera_start():
    ok = _publish_dashboard_command("camera_start")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/camera/stop', methods=['POST'])
def dashboard_camera_stop():
    ok = _publish_dashboard_command("camera_stop")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/demo/pir', methods=['POST'])
def dashboard_demo_pir():
    sensor = str(request.form.get("sensor", "DPIR1")).strip().upper()
    if sensor not in {"DPIR1", "DPIR2", "DPIR3"}:
        return redirect(url_for("dashboard_page", status="invalid_demo"))
    ok = _publish_dashboard_command("demo_pir", {"sensor": sensor})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/demo/ds', methods=['POST'])
def dashboard_demo_ds():
    sensor = str(request.form.get("sensor", "DS1")).strip().upper()
    state = str(request.form.get("state", "1")).strip()
    if sensor not in {"DS1", "DS2"} or state not in {"0", "1"}:
        return redirect(url_for("dashboard_page", status="invalid_demo"))
    ok = _publish_dashboard_command("demo_ds", {"sensor": sensor, "state": state})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/demo/gsg', methods=['POST'])
def dashboard_demo_gsg():
    ok = _publish_dashboard_command("demo_gsg")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/demo/person', methods=['POST'])
def dashboard_demo_person():
    doorway = str(request.form.get("doorway", "1")).strip()
    direction = str(request.form.get("direction", "enter")).strip().lower()
    if doorway not in {"1", "2"} or direction not in {"enter", "exit"}:
        return redirect(url_for("dashboard_page", status="invalid_demo"))
    ok = _publish_dashboard_command("demo_person", {"doorway": doorway, "direction": direction})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


def create_app(
    mqtt_config: Dict[str, Any],
    influxdb_config: Dict[str, Any],
    camera_config: Optional[Dict[str, Any]] = None,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Flask:

    global bridge
    
    if bridge is None:
        bridge = MQTTInfluxDBBridge(
            mqtt_config,
            influxdb_config,
            _configured_simulated(runtime_settings or {}),
        )
        bridge.connect_influxdb()
        bridge.connect_mqtt()
    else:
        print("[Server] Bridge already initialized, reusing existing connection")
        bridge.configured_simulated = _configured_simulated(runtime_settings or {})
    
    app.config["camera_config"] = camera_config or {}
    return app


def main():

    import sys
    import os
    from settings import load_settings
    
    # Load settings (SETTINGS_PATH for Docker)
    settings_path = os.environ.get('SETTINGS_PATH', '')
    if not settings_path or not os.path.exists(settings_path):
        settings_path = 'settings.json'
    if not os.path.exists(settings_path):
        parent_path = os.path.join(os.path.dirname(__file__), '..', 'settings.json')
        if os.path.exists(parent_path):
            settings_path = parent_path

    try:
        settings = load_settings(settings_path)
    except Exception as e:
        print(f"Error loading settings: {e}")
        sys.exit(1)
    
    mqtt_config = settings.get('mqtt', {})
    influxdb_config = settings.get('influxdb', {})
    camera_config = settings.get('CAMERA', {})
    grafana_url = os.environ.get("GRAFANA_URL", "http://localhost:3000")
    
    if not mqtt_config or not influxdb_config:
        print("Error: MQTT or InfluxDB configuration missing in settings.json")
        sys.exit(1)
    
    app = create_app(mqtt_config, influxdb_config, camera_config, settings)
    app.config["grafana_url"] = grafana_url
    
    print("[Server] Starting Flask server on http://localhost:5001")
    try:

        app.run(host='0.0.0.0', port=5001, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        if bridge:
            bridge.disconnect()


if __name__ == '__main__':
    main()
