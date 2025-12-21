import time
import random

def generate_values(initial_value=25):
    value = initial_value
    while True:
        time.sleep(random.uniform(0.5, 3))
        value = random.randint(1, 50)
        yield value

def run_dus1_simulator(callback, stop_event):
    for dust_value in generate_values():
        callback(dust_value)
        if stop_event.is_set():
            break