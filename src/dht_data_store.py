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
    with _lock:
        _dht_data[dht_id] = {
            'humidity': humidity,
            'temperature': temperature,
            'timestamp': threading.current_thread().ident
        }


def get_dht_data(dht_id: str) -> Optional[Dict]:
    with _lock:
        return _dht_data.get(dht_id, {}).copy()


def get_all_dht_data() -> Dict:
    with _lock:
        return {k: v.copy() for k, v in _dht_data.items()}
