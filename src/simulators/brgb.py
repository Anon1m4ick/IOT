"""
Simulator for BRGB (RGB LED) actuator
Simulates RGB LED color changes
"""

# Global state for simulator
_current_color = "OFF"


def set_brgb_color(color_name):
    """
    Set RGB LED color (simulator).
    
    Args:
        color_name: Color name ("OFF", "WHITE", "RED", "GREEN", "BLUE", "YELLOW", "PURPLE", "LIGHT_BLUE")
    """
    global _current_color
    _current_color = color_name
    print(f"[BRGB Simulator] Color set to: {color_name}")


def get_brgb_color():
    """Get current RGB LED color (simulator)"""
    return _current_color


def set_color_by_number(number):
    """
    Set color based on button number (simulator).
    
    Args:
        number: Button number (0-9)
    """
    color_map = {
        0: "OFF",
        1: "WHITE",
        2: "RED",
        3: "GREEN",
        4: "BLUE",
        5: "YELLOW",
        6: "PURPLE",
        7: "LIGHT_BLUE",
        8: "OFF",
        9: "WHITE"
    }
    
    if number in color_map:
        set_brgb_color(color_map[number])
        return True
    return False
