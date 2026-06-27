import time
import random

def generate_values(initial_temp=25, initial_humidity=45):
    temperature = initial_temp
    humidity = initial_humidity
    while True:
        temperature = temperature + random.randint(-1, 1)
        humidity = humidity + random.randint(-1, 1)
        if temperature < 18:
            temperature = 18
        if temperature > 30:
            temperature = 30
        if humidity < 35:
            humidity = 35
        if humidity > 65:
            humidity = 65
        yield humidity, temperature

def run_dht2_simulator(delay, callback, stop_event, simulator_scheduler=None):
    for h, t in generate_values():
        if simulator_scheduler:
            if not simulator_scheduler.wait_for_turn("DHT2"):
                break
        else:
            time.sleep(delay)  # Delay between readings (adjust as needed)
        callback(h, t, "DHTLIB_OK")
        if stop_event.is_set():
            break
