import time
import random

def generate_values(initial_value=0):
    state = initial_value
    while True:
        time.sleep(random.uniform(0.5, 3))
        if random.random() < 0.5:
            state = 1 - state
        yield state

def run_dpir1_simulator(callback, stop_event):
    for dpir1_state in generate_values():
        if dpir1_state == 1:
            callback("Motion detected")
        if stop_event.is_set():
            break