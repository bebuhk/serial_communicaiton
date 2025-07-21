# date: 2025-07-15
# author : bebu
# description: this codes reads the sensor data (from a vaisala GMP343). (only read_sensor() 
#  required if connection was already established and sensor continuously connceted to power. 
#  otherwise connect sensor to power during the 4 sec activation.)

import serial
import time
import threading

# Serial port configuration
PORT = "COM5" # Inlet
PORT = "COM6" # Outlet
BAUDRATE = 19200
TIMEOUT = 1  # seconds

# Connect to the serial port
ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)

def activate_sensor():
    """
    Send repeated 'Z' characters to activate the Vaisala GMP343 sensor.
    Equivalent to holding CAPSLOCK+Z in PuTTY.
    """
    print("Activating sensor by sending repeated 'Z' characters...")
    for _ in range(30):  # Send 'Z' for ~3 seconds
        ser.write(b'Z')
        time.sleep(0.1)
    print("Activation sequence complete.\n")

def read_sensor():
    """
    Continuously read lines from the sensor.
    """
    print("Reading from sensor:")
    try:
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(f"Received: {line}")
    except KeyboardInterrupt:
        print("Stopped reading.")
        ser.close()

def send_command(cmd: str):
    """
    Send a command to the sensor.
    """
    ser.write((cmd + "\r\n").encode())

# --- Main routine ---
if __name__ == "__main__":
    time.sleep(2)  # Wait for serial port to settle
    activate_sensor()
    time.sleep(1)   # Give sensor time to respond

    # Example: list parameters and then start continuous measurement
    send_command("param")
    time.sleep(2)

    send_command("r")

    # Start reading sensor output
    read_sensor()

