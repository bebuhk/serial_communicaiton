import serial
import time
import csv
import threading
from datetime import datetime

# Serial port configurations
PORTS = {
    "CO2_outlet_ppm": "COM4",
    "CO2_inlet_ppm": "COM3",
}
BAUDRATE = 19200
TIMEOUT = 1

# Global data store
sensor_data = {
    "CO2_inlet_ppm": None,
    "CO2_outlet_ppm": None
}

# Activation function
def activate_sensor(ser):
    for _ in range(30):
        ser.write(b'Z')
        time.sleep(0.1)

# Command sender
def send_command(ser, cmd: str):
    ser.write((cmd + "\r\n").encode())

# Reader thread for each sensor
def sensor_reader(sensor_name, port):
    ser = serial.Serial(port, BAUDRATE, timeout=TIMEOUT)
    time.sleep(2)
    activate_sensor(ser)
    time.sleep(1)
    send_command(ser, "r")
    time.sleep(1)
    send_command(ser, "r") # first one fails
    print(f"[{sensor_name}] Active on {port}")

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                sensor_data[sensor_name] = line
        except serial.SerialException as e:
            print(f"Serial error on {sensor_name}: {e}")
            break

# Logger thread
def logger():
    logfile = "dual_co2_log.csv"
    print(f"Logging data to: {logfile}")
    with open(logfile, mode='w', newline='', buffering=1) as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "CO2_inlet_ppm", "CO2_outlet_ppm"])
        try:
            while True:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                row = [
                    timestamp,
                    sensor_data["CO2_inlet_ppm"],
                    sensor_data["CO2_outlet_ppm"]
                ]
                writer.writerow(row)
                print(f"{timestamp} | Inlet: {row[1]} ppm | Outlet: {row[2]} ppm")
                time.sleep(1)
        except KeyboardInterrupt:
            print("Logging stopped.")
            return

# Main routine
if __name__ == "__main__":
    # Start reader threads
    threads = []
    for name, port in PORTS.items():
        t = threading.Thread(target=sensor_reader, args=(name, port), daemon=True)
        t.start()
        threads.append(t)

    # Start logger thread
    logger()
