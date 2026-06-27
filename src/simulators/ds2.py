import time
import random


def generate_values(initial_value=0):
    """Bias toward closed (0): door opens infrequently and closes quickly."""
    state = initial_value
    while True:
        if state == 1:
            time.sleep(random.uniform(0.6, 1.4))
            if random.random() < 0.92:
                state = 0
        else:
            time.sleep(random.uniform(6.0, 14.0))
            if random.random() < 0.06:
                state = 1
        yield int(state)

def run_ds2_simulator(callback, stop_event, simulator_scheduler=None):
    if simulator_scheduler:
        state = 0
        slot_count = 0
        while not stop_event.is_set():
            if not simulator_scheduler.wait_for_turn("DS2"):
                break
            slot_count += 1
            if state == 0 and slot_count % 14 == 0:
                state = 1
                callback("Button Pressed")
            elif state == 1:
                state = 0
                callback("Button Released")
        return

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
