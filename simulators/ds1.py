import time
import random


def generate_values(initial_value=0):
    state = initial_value
    while True:
        time.sleep(random.uniform(0.5, 3))
        if random.random() < 0.5:
            state = 1 - state
        yield state

def run_ds1_simulator(delay, callback, stop_event):
    for button_state in generate_values():
        if button_state == 1:
            callback("Button Pressed")
        if stop_event.is_set():
            break

