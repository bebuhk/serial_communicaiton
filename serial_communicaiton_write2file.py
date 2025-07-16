# date: 2025-07-15
# author : bebu
# description: this codes reads the sensor data (from a vaisala GMP343). (only read_sensor() 
#  required if connection was already established and sensor continuously connceted to power. 
#  otherwise connect sensor to power during the 4 sec activation.) 
#  code writes data to file "log_files/co2_log.csv"

import serial
import time
import csv
from datetime import datetime

# --- Serial Configuration ---
PORT = "COM3"
BAUDRATE = 19200
TIMEOUT = 1  # seconds

# --- Initialize Serial Port ---
ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
time.sleep(2)  # Allow the connection to settle

# --- Activate Sensor ---
def activate_sensor():
    print("Activating sensor by sending repeated 'Z' characters...")
    for _ in range(30):  # ~3 seconds of repeated Z
        ser.write(b'Z')
        time.sleep(0.1)
    print("Activation sequence complete.\n")
    ser.write(b'\n')

# --- Send Command ---
def send_command(cmd: str):
    ser.write((cmd + "\r\n").encode())

# --- Read and Log Sensor Data ---
def read_sensor_and_log():
    logfile = "log_files/co2_log.csv"
    print(f"Logging data to: {logfile}")
    
    # Open CSV and write header
    with open(logfile, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "CO2_Value_ppm"])

        try:
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    writer.writerow([timestamp, line])
                    file.flush()  # Immediately write to disk
                    print(f"{timestamp} | {line}")
        except KeyboardInterrupt:
            print("Logging stopped by user.")
            ser.close()

# --- Main Execution ---
if __name__ == "__main__":
    activate_sensor()
    time.sleep(2)
    send_command(">r")  # Start real-time measurement
    time.sleep(2)
    send_command(">r")  # Start real-time measurement (first one failes)
    read_sensor_and_log()
