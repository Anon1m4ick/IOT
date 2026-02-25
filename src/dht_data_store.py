"""
Shared data store for DHT sensor readings.
Used by LCD component to access DHT1, DHT2, DHT3 data.
"""
import threading
from typing import Optional, Dict

# Thread-safe data store
_dht_data = {
    'DHT1': {'humidity': None, 'temperature': None, 'timestamp': None},
    'DHT2': {'humidity': None, 'temperature': None, 'timestamp': None},
    'DHT3': {'humidity': None, 'temperature': None, 'timestamp': None}
}
_lock = threading.Lock()


def update_dht_data(dht_id: str, humidity: float, temperature: float):
    """Update DHT sensor data in the shared store."""
    with _lock:
        _dht_data[dht_id] = {
            'humidity': humidity,
            'temperature': temperature,
            'timestamp': threading.current_thread().ident
        }


def get_dht_data(dht_id: str) -> Optional[Dict]:
    """Get DHT sensor data from the shared store."""
    with _lock:
        return _dht_data.get(dht_id, {}).copy()


def get_all_dht_data() -> Dict:
    """Get all DHT sensor data."""
    with _lock:
        return {k: v.copy() for k, v in _dht_data.items()}
