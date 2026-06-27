import random
import time


def run_dus1_simulator(callback, stop_event, simulator_scheduler=None):
    """Simulate door distance changes with slower updates."""
    min_distance = 0
    max_distance = 50
    current_distance = min_distance
    is_opening = True

    while not stop_event.is_set():
        if simulator_scheduler and not simulator_scheduler.wait_for_turn("DUS1"):
            break

        step = random.uniform(2.0, 5.0)

        if is_opening:
            current_distance += step
            if current_distance >= max_distance:
                current_distance = max_distance
                callback("Door opened")
                is_opening = False
        else:
            current_distance -= step
            if current_distance <= min_distance:
                current_distance = min_distance
                callback("Door closed")
                is_opening = True

        callback(int(current_distance))
        if not simulator_scheduler:
            time.sleep(random.uniform(1.2, 2.0))
