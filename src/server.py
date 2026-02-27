import json
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request, render_template
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


class MQTTInfluxDBBridge:
    """
    Bridge between MQTT and InfluxDB.
    Thread-safe implementation.
    """
    
    def __init__(self, mqtt_config: Dict[str, Any], influxdb_config: Dict[str, Any]):
        """
        Initialize the bridge.
        
        Args:
            mqtt_config: MQTT broker configuration
            influxdb_config: InfluxDB configuration
        """
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
        """
        Callback when MQTT message is received.
        This runs in MQTT client's thread, so we need to be thread-safe.
        """
        try:
            print(f"[Server] Received message on topic: {msg.topic}")  # Отладочный принт
            payload = json.loads(msg.payload.decode('utf-8'))
            topic = msg.topic
            
            # Extract sensor type from topic
            sensor_type = topic.split('/')[-1].upper()
            
            print(f"[Server] Processing {sensor_type} data: value={payload.get('value')}, simulated={payload.get('simulated')}")
            
            # Store in InfluxDB
            self._store_in_influxdb(sensor_type, payload)
            
        except json.JSONDecodeError as e:
            print(f"[Server] Error decoding JSON: {e}")
        except Exception as e:
            print(f"[Server] Error processing message: {e}")
    
    def _store_in_influxdb(self, sensor_type: str, data: Dict[str, Any]):
        """
        Store data in InfluxDB.
        Minimal locking - only during write operation.
        """
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
    
    def _convert_value(self, value: Any) -> float:
        """Convert value to float for InfluxDB."""
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            # Try to convert string to number
            try:
                return float(value)
            except ValueError:
                # For non-numeric strings (like button presses), use hash
                return float(hash(value) % 10000)
        else:
            return 0.0
    
    def _convert_dms_value(self, button_char: str) -> float:
        """
        Convert DMS button character to numeric value for graphing.
        Mapping: 0-9 = 0-9, A=10, B=11, C=12, D=13, *=14, #=15
        """
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
        """Connect to MQTT broker."""
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
        """Connect to InfluxDB."""
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
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'mqtt_connected': bridge.connected if bridge else False,
        'influxdb_connected': bridge.write_api is not None if bridge else False,
        'camera_enabled': _camera_enabled(),
    })


@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    """Get list of available sensors."""
    return jsonify({
        'sensors': ['DS1', 'DUS1', 'DPIR1', 'DMS']
    })


@app.route('/api/actuators/dl', methods=['POST'])
def control_door_light():
    """
    Control door light actuator.
    For Grafana integration.
    """
    data = request.get_json() or {}
    state = data.get('state', 'off')
    
    # Here you would send MQTT command to control the actuator
    # For now, just return success
    return jsonify({
        'status': 'success',
        'actuator': 'DL',
        'state': state,
        'message': f'Door light set to {state}'
    })


@app.route('/api/actuators/db', methods=['POST'])
def control_door_buzzer():
    """
    Control door buzzer actuator.
    For Grafana integration.
    """
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


def create_app(
    mqtt_config: Dict[str, Any],
    influxdb_config: Dict[str, Any],
    camera_config: Optional[Dict[str, Any]] = None,
) -> Flask:
    """
    Create and configure Flask app with MQTT-InfluxDB bridge.
    
    Args:
        mqtt_config: MQTT broker configuration
        influxdb_config: InfluxDB configuration
    
    Returns:
        Configured Flask app
    """
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
    """Main function to run the server."""
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
    
    if not mqtt_config or not influxdb_config:
        print("Error: MQTT or InfluxDB configuration missing in settings.json")
        sys.exit(1)
    
    app = create_app(mqtt_config, influxdb_config, camera_config)
    
    print("[Server] Starting Flask server on http://localhost:5001")
    try:

        app.run(host='0.0.0.0', port=5001, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        if bridge:
            bridge.disconnect()


if __name__ == '__main__':
    main()
