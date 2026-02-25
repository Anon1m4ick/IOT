"""
Simulator for LCD display
"""
import time
import threading
from dht_data_store import get_dht_data


def run_lcd_simulator(rotation_interval, callback, stop_event):
    """
    Simulate LCD display by printing to console.
    Rotates between DHT1, DHT2, DHT3 every rotation_interval seconds.
    
    Args:
        rotation_interval: Seconds to display each DHT before rotating
        callback: Callback function to call with display updates
        stop_event: Threading event to stop the loop
    """
    dht_sensors = ['DHT1', 'DHT2', 'DHT3']
    current_index = 0
    
    while not stop_event.is_set():
        try:
            # Get current DHT sensor data
            dht_id = dht_sensors[current_index]
            data = get_dht_data(dht_id)
            
            if data and data.get('humidity') is not None and data.get('temperature') is not None:
                humidity = data['humidity']
                temperature = data['temperature']
                
                # Format display text - одна строка с температурой и влажностью
                display_text = f"{dht_id}: T:{temperature:.1f}C H:{humidity:.1f}%"
                if callback:
                    callback(display_text)
                else:
                    print(f"[LCD Simulator] {display_text}")
            else:
                # No data available for this sensor
                display_text = f"{dht_id}: No data\nWaiting..."
                if callback:
                    callback(display_text)
                else:
                    print(f"[LCD Simulator] {display_text}")
            
            # Rotate to next sensor after rotation_interval seconds
            for _ in range(int(rotation_interval * 10)):  # Check every 0.1 seconds
                if stop_event.is_set():
                    break
                time.sleep(0.1)
            
            # Move to next sensor
            current_index = (current_index + 1) % len(dht_sensors)
            
        except Exception as e:
            print(f"[LCD Simulator] Error: {e}")
            time.sleep(1)
