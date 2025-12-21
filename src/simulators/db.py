import time

def activate_db(frequency: int = 1000, duration: int = 1):
    print(f"Buzzer activated: {frequency}Hz for {duration}s")
    time.sleep(duration)
    print("Buzzer stopped")
    return f"Buzzer activated: {frequency}Hz for {duration}s"
