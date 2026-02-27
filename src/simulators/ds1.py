import time
import random


def generate_values(initial_value=0):
    """Bias toward closed (0): door rarely opens and closes again quickly (< 5s)."""
    state = initial_value
    while True:
        if state == 1:
            time.sleep(random.uniform(0.4, 1.5))  # short "open" time
            if random.random() < 0.85:
                state = 0
        else:
            time.sleep(random.uniform(2.0, 5.0))  # longer intervals between "opens"
            if random.random() < 0.12:
                state = 1
        yield int(state)

# def run_ds1_simulator(callback, stop_event):
#     for button_state in generate_values():
#         if button_state == 1:
#             callback("Button Pressed")
#         if stop_event.is_set():
#             break

def run_ds1_simulator(callback, stop_event):
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
