"""
Simulator for GSG (Gyroscope Sensor)
Simulates motion detection (returns 0 or 1)
"""
import time
import random


def run_gsg_simulator(interval, callback, stop_event):
    """
    Simulate GSG sensor by generating random 0/1 values.
    
    Args:
        interval: Reading interval in seconds
        callback: Callback function to call with movement status (0 or 1)
        stop_event: Threading event to stop the loop
    """
    while not stop_event.is_set():
        try:
            # Randomly generate 0 or 1 (with higher probability of 0 for "normal" state)
            # 20% chance of movement (1), 80% chance of no movement (0)
            movement = 1 if random.random() < 0.05 else 0
            callback(movement)
            time.sleep(interval)
        except Exception as e:
            print(f"[GSG Simulator] Error: {e}")
            time.sleep(1)
