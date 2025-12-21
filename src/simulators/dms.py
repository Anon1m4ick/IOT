import time
import random

def generate_values(initial_value=""):
    buttons = ['1', '2', '3', 'A', '4', '5', '6', 'B', '7', '8', '9', 'C', '*', '0', '#', 'D']
    while True:
        time.sleep(random.uniform(1, 5))
        if random.random() < 0.3:
            value = random.choice(buttons)
            yield value
        else:
            yield None

def run_dms_simulator(callback, stop_event):
    for button in generate_values():
        if button is not None:
            callback(f"Button pressed: {button}")
        if stop_event.is_set():
            break

