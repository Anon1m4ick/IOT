"""
Simplified MPU6050 driver for basic accelerometer and gyroscope reading
Only includes essential methods for motion detection
"""
import time
import ctypes

try:
    import smbus
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False
    smbus = None


class MPU6050_Simple:
    """Simplified MPU6050 driver for motion detection"""
    
    # Default I2C address
    MPU6050_DEFAULT_ADDRESS = 0x68
    
    # Register addresses
    MPU6050_RA_PWR_MGMT_1 = 0x6B
    MPU6050_RA_ACCEL_XOUT_H = 0x3B
    MPU6050_RA_GYRO_XOUT_H = 0x43
    
    # Power management bits
    MPU6050_PWR1_SLEEP_BIT = 6
    MPU6050_PWR1_CLKSEL_BIT = 2
    MPU6050_PWR1_CLKSEL_LENGTH = 3
    
    # Clock sources
    MPU6050_CLOCK_PLL_XGYRO = 0x01
    
    def __init__(self, bus=1, address=None):
        """
        Initialize MPU6050.
        
        Args:
            bus: I2C bus number (default 1)
            address: I2C address (default 0x68)
        """
        if not SMBUS_AVAILABLE:
            raise RuntimeError("smbus is not available. This code must run on a Raspberry Pi.")
        
        self.address = address if address else self.MPU6050_DEFAULT_ADDRESS
        self.bus = smbus.SMBus(bus)
        
        # Wake up MPU6050
        self.wake_up()
        
        # Set clock source to gyro
        self.set_clock_source(self.MPU6050_CLOCK_PLL_XGYRO)
    
    def wake_up(self):
        """Wake up MPU6050 from sleep mode"""
        current = self.bus.read_byte_data(self.address, self.MPU6050_RA_PWR_MGMT_1)
        # Clear sleep bit
        current &= ~(1 << self.MPU6050_PWR1_SLEEP_BIT)
        self.bus.write_byte_data(self.address, self.MPU6050_RA_PWR_MGMT_1, current)
        time.sleep(0.01)  # Wait for MPU to wake up
    
    def set_clock_source(self, source):
        """Set clock source"""
        current = self.bus.read_byte_data(self.address, self.MPU6050_RA_PWR_MGMT_1)
        # Clear clock select bits
        current &= ~((0x07) << self.MPU6050_PWR1_CLKSEL_BIT)
        # Set new clock source
        current |= (source << self.MPU6050_PWR1_CLKSEL_BIT)
        self.bus.write_byte_data(self.address, self.MPU6050_RA_PWR_MGMT_1, current)
    
    def get_acceleration(self):
        """
        Read accelerometer data.
        
        Returns:
            List [x, y, z] in raw sensor units
        """
        raw_data = self.bus.read_i2c_block_data(
            self.address, self.MPU6050_RA_ACCEL_XOUT_H, 6
        )
        accel = [0] * 3
        accel[0] = ctypes.c_int16(raw_data[0] << 8 | raw_data[1]).value
        accel[1] = ctypes.c_int16(raw_data[2] << 8 | raw_data[3]).value
        accel[2] = ctypes.c_int16(raw_data[4] << 8 | raw_data[5]).value
        return accel
    
    def get_rotation(self):
        """
        Read gyroscope data.
        
        Returns:
            List [x, y, z] in raw sensor units
        """
        raw_data = self.bus.read_i2c_block_data(
            self.address, self.MPU6050_RA_GYRO_XOUT_H, 6
        )
        gyro = [0] * 3
        gyro[0] = ctypes.c_int16(raw_data[0] << 8 | raw_data[1]).value
        gyro[1] = ctypes.c_int16(raw_data[2] << 8 | raw_data[3]).value
        gyro[2] = ctypes.c_int16(raw_data[4] << 8 | raw_data[5]).value
        return gyro
