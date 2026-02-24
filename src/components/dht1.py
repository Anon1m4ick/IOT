import threading
import time
from simulators.dht1 import run_dht1_simulator

def dht1_callback(humidity, temperature, code):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Code: {code}")
    print(f"Humidity: {humidity}%")
    print(f"Temperature: {temperature}°C")

def run_dht1(settings, threads, stop_event, callback=None, mqtt_publisher=None):
    if callback is None:
        callback = dht1_callback
    
    def enhanced_callback(humidity, temperature, code):
        callback(humidity, temperature, code)
        if mqtt_publisher:
            # Send humidity
            mqtt_publisher.add_sensor_data("DHT1_HUMIDITY", humidity, settings['simulated'])
            # Send temperature
            mqtt_publisher.add_sensor_data("DHT1_TEMPERATURE", temperature, settings['simulated'])
    
    if settings['simulated']:
        print("Starting dht1 simulator")
        dht1_thread = threading.Thread(target=run_dht1_simulator, args=(2, enhanced_callback, stop_event))
        dht1_thread.start()
        threads.append(dht1_thread)
        print("Dht1 simulator started")
    else:
        from sensors.dht1 import run_dht1_loop, DHT1
        print("Starting dht1 loop")
        dht = DHT1(settings['pin'])
        dht1_thread = threading.Thread(target=run_dht1_loop, args=(dht, 2, enhanced_callback, stop_event))
        dht1_thread.start()
        threads.append(dht1_thread)
        print("Dht1 loop started")
