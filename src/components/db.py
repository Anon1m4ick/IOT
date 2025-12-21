import threading
import time
from typing import Dict
from simulators.db import activate_db

def run_db(config: Dict):
    if config["simulated"]:
        return {
            "activate": lambda freq, dur: activate_db(freq, dur),
            "simulated": True
        }
    else:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config['pin'], GPIO.OUT)
        
        def activate(frequency: int = 1000, duration: int = 1):
            GPIO.output(config['pin'], GPIO.HIGH)
            time.sleep(duration)
            GPIO.output(config['pin'], GPIO.LOW)
            return f"Buzzer activated: {frequency}Hz for {duration}s"
        
        return {
            "activate": activate,
            "simulated": False
        }
