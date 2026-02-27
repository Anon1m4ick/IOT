import threading
import time
import json
import queue
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt


class MQTTPublisher:
    
    def __init__(self, mqtt_config: Dict[str, Any], device_config: Dict[str, Any]):

        self.mqtt_config = mqtt_config
        self.device_config = device_config
        self.batch_size = mqtt_config.get('batch_size', 10)
        self.batch_interval = mqtt_config.get('batch_interval_seconds', 5)
        
        # Thread-safe queue for sensor data
        self.data_queue = queue.Queue()
        
        # Lock for MQTT client operations (minimal locking)
        self.mqtt_lock = threading.Lock()
        
        self.client = None
        self.connected = False
        self.connection_established = threading.Event()

        # Daemon thread control
        self.stop_event = threading.Event()
        self.daemon_thread = None

    def _on_connect(self, client, userdata, flags, rc, properties=None):

        if rc == 0:
            self.connected = True
            self.connection_established.set()
            print(f"[MQTT] Connected to broker")
        else:
            self.connected = False
            self.connection_established.clear()
            try:
                code = int(rc)
            except (TypeError, ValueError):
                code = getattr(rc, 'getName', lambda: str(rc))()
            print(f"[MQTT] Connection failed: {code}")

    def _on_disconnect(self, client, userdata, rc, properties=None):

        self.connected = False
        self.connection_established.clear()
        print(f"[MQTT] Disconnected from broker")
    
    def connect(self):

        if self.client and self.connected:
            return
        
        try:
            self.client = mqtt.Client(
                client_id=self.mqtt_config.get('client_id', 'pi1_client'),
                protocol=mqtt.MQTTv5,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            broker_host = self.mqtt_config.get('broker_host', 'localhost')
            broker_port = self.mqtt_config.get('broker_port', 1883)
            
            self.client.connect(broker_host, broker_port, keepalive=60)
            self.client.loop_start()
            time.sleep(1.0)
            
        except Exception as e:
            print(f"[MQTT] Error connecting: {e}")
            self.connected = False
    
    def add_sensor_data(self, sensor_type: str, value: Any, simulated: bool, 
                       timestamp: Optional[float] = None):

        if timestamp is None:
            timestamp = time.time()
        
        data = {
            'sensor_type': sensor_type,
            'value': value,
            'simulated': simulated,
            'timestamp': timestamp,
            'pi_id': self.device_config.get('pi_id', 'PI1'),
            'device_name': self.device_config.get('device_name', 'Unknown')
        }
        
        # Non-blocking put (will raise full exception if queue is full, but we handle it)
        try:
            self.data_queue.put_nowait(data)
        except queue.Full:
            print(f"[MQTT] Warning: Queue full, dropping data from {sensor_type}")
    
    def _send_batch(self, batch: list):

        if not self.connection_established.is_set() or not self.client:
            return
        
        topics = self.mqtt_config.get('topics', {})
        
        for data in batch:
            if self.stop_event.is_set():
                break
            sensor_type = data['sensor_type']
            topic = topics.get(sensor_type, f"sensors/{sensor_type.lower()}")
            
            message = {
                'value': data['value'],
                'timestamp': data['timestamp'],
                'pi_id': data['pi_id'],
                'device_name': data['device_name'],
                'simulated': data['simulated']
            }
            message_json = json.dumps(message)
            
            try:
                with self.mqtt_lock:
                    if self.stop_event.is_set():
                        break
                    result = self.client.publish(topic, message_json, qos=1)
                    if result.rc != mqtt.MQTT_ERR_SUCCESS:
                        print(f"[MQTT] Failed to publish to {topic}: {result.rc}")
            except Exception as e:
                print(f"[MQTT] Error publishing to {topic}: {e}")
    
    def _daemon_worker(self):

        # Явно ждём соединения: колбэк on_connect выполняется в другом потоке
        if not self.connection_established.wait(timeout=15):
            print("[MQTT] Daemon: still not connected after 15s, will retry when connected")
        batch = []
        last_send_time = time.time()

        while not self.stop_event.is_set():
            try:
                # Try to get data from queue (non-blocking with timeout)
                try:
                    data = self.data_queue.get(timeout=0.1)
                    batch.append(data)
                except queue.Empty:
                    pass
                
                current_time = time.time()
                time_since_last_send = current_time - last_send_time
                
                # Send batch if:
                # 1. Batch size reached, OR
                # 2. Time interval elapsed and batch is not empty
                should_send = (
                    len(batch) >= self.batch_size or
                    (time_since_last_send >= self.batch_interval and len(batch) > 0)
                )
                
                if should_send and batch:
                    self._send_batch(batch)
                    batch = []
                    last_send_time = current_time
                
                # Reconnect attempt when not connected (avoids permanent failure)
                if not self.connection_established.is_set() and self.client:
                    try:
                        with self.mqtt_lock:
                            if not self.connection_established.is_set() and self.client:
                                self.client.reconnect()
                    except Exception:
                        pass
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[MQTT] Error in daemon worker: {e}")
                time.sleep(0.5)
        
        # Send remaining batch before stopping
        if batch:
            self._send_batch(batch)
    
    def start(self):

        self.connect()
        
        if not self.connected:
            print("[MQTT] Warning: Not connected, daemon will retry")
        
        # Start daemon thread
        self.daemon_thread = threading.Thread(target=self._daemon_worker, daemon=True)
        self.daemon_thread.start()
        print("[MQTT] Daemon thread started")
    
    def stop(self):

        self.stop_event.set()
        
        if self.daemon_thread:
            self.daemon_thread.join(timeout=2)
        
        if self.client:
            try:
                with self.mqtt_lock:
                    self.client.loop_stop()
                    if self.connected:
                        self.client.disconnect()
            except Exception as e:
                print(f"[MQTT] Error during disconnect: {e}")
        
        print("[MQTT] Publisher stopped")
