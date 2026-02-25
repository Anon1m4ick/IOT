import threading
import time
from simulators.dht2 import run_dht2_simulator
from dht_data_store import update_dht_data

def dht2_callback(humidity, temperature, code):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Code: {code}")
    print(f"Humidity: {humidity}%")
    print(f"Temperature: {temperature}°C")

def run_dht2(settings, threads, stop_event, callback=None, mqtt_publisher=None):
    if callback is None:
        callback = dht2_callback
    
    def enhanced_callback(humidity, temperature, code):
        callback(humidity, temperature, code)
        # Store data in shared store for LCD
        update_dht_data('DHT2', humidity, temperature)
        if mqtt_publisher:
            # Send humidity
            mqtt_publisher.add_sensor_data("DHT2_HUMIDITY", humidity, settings['simulated'])
            # Send temperature
            mqtt_publisher.add_sensor_data("DHT2_TEMPERATURE", temperature, settings['simulated'])
    
    if settings['simulated']:
        print("Starting dht2 simulator")
        dht2_thread = threading.Thread(target=run_dht2_simulator, args=(2, enhanced_callback, stop_event))
        dht2_thread.start()
        threads.append(dht2_thread)
        print("Dht2 simulator started")
    else:
        from sensors.dht2 import run_dht2_loop, DHT2
        print("Starting dht2 loop")
        dht = DHT2(settings['pin'])
        dht2_thread = threading.Thread(target=run_dht2_loop, args=(dht, 2, enhanced_callback, stop_event))
        dht2_thread.start()
        threads.append(dht2_thread)
        print("Dht2 loop started")
