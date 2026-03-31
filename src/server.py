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
    
    def __init__(self, mqtt_config: Dict[str, Any], influxdb_config: Dict[str, Any]):

        self.mqtt_config = mqtt_config
        self.influxdb_config = influxdb_config
        
        
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

        self.state_lock = threading.Lock()
        self.latest_sensor_values: Dict[str, Any] = {}
        self.notifications = deque(maxlen=200)
        self.state = {
            "alarm_active": False,
            "timer_remaining_seconds": 0,
            "brgb_color": "OFF",
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
            self.state["updated_at"] = timestamp

            if sensor_type == "4SD":
                try:
                    self.state["timer_remaining_seconds"] = max(0, int(float(value)))
                except Exception:
                    pass
            elif sensor_type == "BRGB":
                self.state["brgb_color"] = str(value).upper()
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

        return {
            "state": state_snapshot,
            "latest_sensors": latest,
            "dht": dht,
            "notifications": notifications,
            "control_topic": self.control_topic,
        }

    def publish_command(self, action: str, payload: Optional[Dict[str, Any]] = None) -> bool:
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
        'sensors': ['DS1', 'DUS1', 'DPIR1', 'DMS']
    })


@app.route('/api/actuators/dl', methods=['POST'])
def control_door_light():

    data = request.get_json() or {}
    state = data.get('state', 'off')
    
    return jsonify({
        'status': 'success',
        'actuator': 'DL',
        'state': state,
        'message': f'Door light set to {state}'
    })


@app.route('/api/actuators/db', methods=['POST'])
def control_door_buzzer():

    data = request.get_json() or {}
    frequency = data.get('frequency', 1000)
    duration = data.get('duration', 1)
    
    return jsonify({
        'status': 'success',
        'actuator': 'DB',
        'frequency': frequency,
        'duration': duration,
        'message': f'Buzzer activated: {frequency}Hz for {duration}s'
    })


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
            "timer_remaining_seconds": 0,
            "brgb_color": "OFF",
            "person_count": 0,
            "updated_at": time.time(),
        },
        "latest_sensors": {},
        "dht": {},
        "notifications": [],
    }
    status = request.args.get("status", "")
    return render_template(
        "dashboard.html",
        state=snapshot.get("state", {}),
        latest_sensors=snapshot.get("latest_sensors", {}),
        dht=snapshot.get("dht", {}),
        notifications=snapshot.get("notifications", []),
        camera_enabled=_camera_enabled(),
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


@app.route('/dashboard/dl', methods=['POST'])
def dashboard_dl():
    state = str(request.form.get("state", "off")).strip().lower()
    if state not in {"on", "off"}:
        return redirect(url_for("dashboard_page", status="invalid_dl"))
    ok = _publish_dashboard_command("dl_set", {"state": state})
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/camera/start', methods=['POST'])
def dashboard_camera_start():
    ok = _publish_dashboard_command("camera_start")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


@app.route('/dashboard/camera/stop', methods=['POST'])
def dashboard_camera_stop():
    ok = _publish_dashboard_command("camera_stop")
    return redirect(url_for("dashboard_page", status="ok" if ok else "mqtt_error"))


def create_app(
    mqtt_config: Dict[str, Any],
    influxdb_config: Dict[str, Any],
    camera_config: Optional[Dict[str, Any]] = None,
) -> Flask:

    global bridge
    
    if bridge is None:
        bridge = MQTTInfluxDBBridge(mqtt_config, influxdb_config)
        bridge.connect_influxdb()
        bridge.connect_mqtt()
    else:
        print("[Server] Bridge already initialized, reusing existing connection")
    
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
    
    app = create_app(mqtt_config, influxdb_config, camera_config)
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
