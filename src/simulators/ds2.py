import time
import random


def generate_values(initial_value=0):
    state = initial_value
    while True:
        time.sleep(random.uniform(0.5, 3))
        if random.random() < 0.5:
            state = 1 - state
        yield int(state)

def run_ds2_simulator(callback, stop_event):
    previous_state = None
    for button_state in generate_values():
        if previous_state is not None and previous_state != button_state:
            if int(button_state) == 1:
                callback("Button Pressed")
            else:
                callback("Button Released")
        previous_state = button_state
        if stop_event.is_set():
            break
