"""
IR component - Infrared receiver for reading remote control commands
"""
import threading
from simulators.ir import run_ir_simulator


def ir_callback(button):
    """Default callback for IR button presses"""
    print(f"IR: Button pressed: {button}")


def run_ir(settings, threads, stop_event, callback=None, mqtt_publisher=None, brgb_handler=None):
    """
    Run IR component.
    
    Args:
        settings: IR settings from settings.json
        threads: List to append thread to
        stop_event: Event to stop the thread
        callback: Optional callback for button presses
        mqtt_publisher: Optional MQTT publisher
        brgb_handler: Optional handler function from BRGB component
    """
    if callback is None:
        callback = ir_callback
    
    def enhanced_callback(button_name):
        """Enhanced callback that also calls BRGB handler and sends to MQTT"""
        callback(button_name)
        # Send to MQTT
        if mqtt_publisher:
            # Send button name as string value
            mqtt_publisher.add_sensor_data("IR", button_name, settings['simulated'])
        # Call BRGB handler if provided
        if brgb_handler:
            brgb_handler(button_name)
    
    if settings['simulated']:
        print("Starting IR simulator (manual mode - use 'ir <0-9>' commands)")
        # In simulation mode, IR only works via manual commands, not random button presses
        # No thread needed - commands are handled via TUI
        print("IR simulator ready (waiting for manual commands)")
    else:
        from sensors.ir import run_ir_loop, IR
        print("Starting IR real hardware")
        ir = IR(settings['pin'])
        ir_thread = threading.Thread(
            target=run_ir_loop,
            args=(ir, enhanced_callback, stop_event)
        )
        ir_thread.start()
        threads.append(ir_thread)
        print("IR real hardware started")
