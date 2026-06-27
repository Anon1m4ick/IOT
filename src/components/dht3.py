import threading
import time
from simulators.dht3 import run_dht3_simulator
from dht_data_store import update_dht_data

def dht3_callback(humidity, temperature, code):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Code: {code}")
    print(f"Humidity: {humidity}%")
    print(f"Temperature: {temperature}°C")

def run_dht3(settings, threads, stop_event, callback=None, mqtt_publisher=None, simulator_scheduler=None):
    if callback is None:
        callback = dht3_callback
    
    def enhanced_callback(humidity, temperature, code):
        callback(humidity, temperature, code)
        # Store data in shared store for LCD
        update_dht_data('DHT3', humidity, temperature)
        if mqtt_publisher:
            # Send humidity
            mqtt_publisher.add_sensor_data("DHT3_HUMIDITY", humidity, settings['simulated'])
            # Send temperature
            mqtt_publisher.add_sensor_data("DHT3_TEMPERATURE", temperature, settings['simulated'])
    
    if settings['simulated']:
        print("Starting dht3 simulator")
        dht3_thread = threading.Thread(target=run_dht3_simulator, args=(2, enhanced_callback, stop_event, simulator_scheduler))
        dht3_thread.start()
        threads.append(dht3_thread)
        print("Dht3 simulator started")
    else:
        from sensors.dht3 import run_dht3_loop, DHT3
        print("Starting dht3 loop")
        dht = DHT3(settings['pin'])
        dht3_thread = threading.Thread(target=run_dht3_loop, args=(dht, 2, enhanced_callback, stop_event))
        dht3_thread.start()
        threads.append(dht3_thread)
        print("Dht3 loop started")
