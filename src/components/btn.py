"""
BTN (Kitchen Button) component.
When not simulated, reads GPIO and calls the given callback on each press
(e.g. 4SD's button_press to add seconds or stop blink).
"""
import threading
from typing import Dict, Callable, Optional


def run_btn(
    settings: Dict,
    threads: list,
    stop_event: threading.Event,
    callback: Optional[Callable[[], None]] = None,
):
    """
    Start BTN: in real mode, GPIO button invokes callback on press.
    In simulated mode no thread is started; use TUI "4sd btn" or API to trigger.
    """
    if settings.get("simulated", True):
        print("[BTN] Simulated mode: use '4sd btn' in TUI or API to add seconds")
        return

    try:
        from sensors.btn import BTN, run_btn_loop
    except ImportError as e:
        print(f"[BTN] Real hardware unavailable: {e}")
        return

    if not callback:
        print("[BTN] No callback (4SD?) - button press will do nothing")

    pin = int(settings.get("pin", 17))
    btn = BTN(pin, press_callback=callback)
    t = threading.Thread(target=run_btn_loop, args=(btn, stop_event), daemon=True)
    t.start()
    threads.append(t)
    print(f"[BTN] Started on GPIO {pin}")
