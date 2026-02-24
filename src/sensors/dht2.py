"""
Real implementation of DHT2 (Temperature and Humidity Sensor - Master Bedroom) using RPi.GPIO
"""
import time
import threading

try:
    import RPi.GPIO as GPIO  # type: ignore
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    GPIO = None


class DHT2:
    """DHT11 temperature and humidity sensor controller"""
    
    DHTLIB_OK = 0
    DHTLIB_ERROR_CHECKSUM = -1
    DHTLIB_ERROR_TIMEOUT = -2
    DHTLIB_INVALID_VALUE = -999
    
    DHTLIB_DHT11_WAKEUP = 0.020  # 18ms
    DHTLIB_TIMEOUT = 0.0001  # 100us
    
    def __init__(self, pin):
        if not GPIO_AVAILABLE:
            raise RuntimeError("RPi.GPIO is not available. This code must run on a Raspberry Pi.")
        
        self.pin = pin
        self.bits = [0, 0, 0, 0, 0]
        self.humidity = 0
        self.temperature = 0
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.HIGH)
    
    def readSensor(self, pin, wakeupDelay):
        """Read DHT sensor, store the original data in bits[]"""
        mask = 0x80
        idx = 0
        self.bits = [0, 0, 0, 0, 0]
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(wakeupDelay)
        GPIO.output(pin, GPIO.HIGH)
        GPIO.setup(pin, GPIO.IN)
        
        loopCnt = self.DHTLIB_TIMEOUT
        t = time.time()
        while GPIO.input(pin) == GPIO.LOW:
            if (time.time() - t) > loopCnt:
                return self.DHTLIB_ERROR_TIMEOUT
        t = time.time()
        while GPIO.input(pin) == GPIO.HIGH:
            if (time.time() - t) > loopCnt:
                return self.DHTLIB_ERROR_TIMEOUT
        for i in range(0, 40, 1):
            t = time.time()
            while GPIO.input(pin) == GPIO.LOW:
                if (time.time() - t) > loopCnt:
                    return self.DHTLIB_ERROR_TIMEOUT
            t = time.time()
            while GPIO.input(pin) == GPIO.HIGH:
                if (time.time() - t) > loopCnt:
                    return self.DHTLIB_ERROR_TIMEOUT
            if (time.time() - t) > 0.00005:
                self.bits[idx] |= mask
            mask >>= 1
            if mask == 0:
                mask = 0x80
                idx += 1
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        return self.DHTLIB_OK
    
    def readDHT11(self):
        """Read DHT sensor, analyze the data of temperature and humidity"""
        rv = self.readSensor(self.pin, self.DHTLIB_DHT11_WAKEUP)
        if rv is not self.DHTLIB_OK:
            self.humidity = self.DHTLIB_INVALID_VALUE
            self.temperature = self.DHTLIB_INVALID_VALUE
            return rv
        self.humidity = self.bits[0]
        self.temperature = self.bits[2] + self.bits[3] * 0.1
        sumChk = ((self.bits[0] + self.bits[1] + self.bits[2] + self.bits[3]) & 0xFF)
        if self.bits[4] is not sumChk:
            return self.DHTLIB_ERROR_CHECKSUM
        return self.DHTLIB_OK
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if GPIO_AVAILABLE:
            GPIO.cleanup()


def parseCheckCode(code):
    """Parse DHT error code to string"""
    if code == 0:
        return "DHTLIB_OK"
    elif code == -1:
        return "DHTLIB_ERROR_CHECKSUM"
    elif code == -2:
        return "DHTLIB_ERROR_TIMEOUT"
    elif code == -999:
        return "DHTLIB_INVALID_VALUE"
    else:
        return f"UNKNOWN_ERROR_{code}"


def run_dht2_loop(dht2_instance, delay, callback, stop_event):
    """
    Run continuous loop reading DHT sensor.
    
    Args:
        dht2_instance: DHT2 instance
        delay: Time between readings in seconds
        callback: Function to call with (humidity, temperature, code)
        stop_event: threading.Event to stop the loop
    """
    if stop_event is None:
        stop_event = threading.Event()
    
    try:
        while not stop_event.is_set():
            check = dht2_instance.readDHT11()
            code = parseCheckCode(check)
            humidity, temperature = dht2_instance.humidity, dht2_instance.temperature
            callback(humidity, temperature, code)
            time.sleep(delay)
    except KeyboardInterrupt:
        print('\n[DHT2] Measurement stopped by user')
        dht2_instance.cleanup()
    except Exception as e:
        print(f'[DHT2] Error: {str(e)}')
        dht2_instance.cleanup()
