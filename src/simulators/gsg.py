"""
Simulator for GSG (Gyroscope Sensor)
Simulates motion detection (returns 0 or 1)
"""
import time
import random


def run_gsg_simulator(interval, callback, stop_event, simulator_scheduler=None):
    """
    Simulate GSG sensor by generating random 0/1 values.
    
    Args:
        interval: Reading interval in seconds
        callback: Callback function to call with movement status (0 or 1)
        stop_event: Threading event to stop the loop
    """
    while not stop_event.is_set():
        try:
            if simulator_scheduler and not simulator_scheduler.wait_for_turn("GSG"):
                break
            # Keep movement events rare to avoid frequent alarm triggers.
            movement = 1 if random.random() < 0.003 else 0
            callback(movement)
            if not simulator_scheduler:
                time.sleep(interval)
        except Exception as e:
            print(f"[GSG Simulator] Error: {e}")
            time.sleep(1)
