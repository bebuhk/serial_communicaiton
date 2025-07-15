import serial
import threading
import time
import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
from collections import deque
from datetime import timedelta

# --- Serial ports ---
PORTS = {
    "CO2_inlet_ppm":  "COM3",
    "CO2_outlet_ppm": "COM4",
}
BAUDRATE = 19200
TIMEOUT = 1

# --- Data buffering for plotting ---
MAX_MINUTES = 30
MAX_POINTS = MAX_MINUTES * 60  # 1 per second


class DualCO2Logger:
    def __init__(self, ports, baudrate=BAUDRATE, timeout=TIMEOUT):
        self.ports = ports
        self.baudrate = baudrate
        self.timeout = timeout
        self.stop_event = threading.Event()
        self.data_lock = threading.Lock()
        self.data = {name: None for name in ports}
        self.serials = {}
        self.threads = []
        self.row_callback = None  # GUI callback: (timestamp, inlet, outlet)

    def _activate_sensor(self, ser):
        for _ in range(30):
            ser.write(b"Z")
            time.sleep(0.1)

    def _reader(self, name, port):
        try:
            ser = serial.Serial(port, self.baudrate, timeout=self.timeout)
            self.serials[name] = ser
        except serial.SerialException as exc:
            print(f"[{name}] cannot open {port}: {exc}")
            return

        time.sleep(2)
        self._activate_sensor(ser)
        time.sleep(1)
        ser.write(b"r\r\n")

        while not self.stop_event.is_set():
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                with self.data_lock:
                    self.data[name] = line
        ser.close()

    def _logger(self, filename):
        with open(filename, "w", newline="", buffering=1) as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", *self.ports.keys()])

            while not self.stop_event.is_set():
                with self.data_lock:
                    timestamp = datetime.now()
                    inlet = self.data["CO2_inlet_ppm"]
                    outlet = self.data["CO2_outlet_ppm"]
                writer.writerow([timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], inlet, outlet])
                f.flush()
                if self.row_callback and inlet and outlet:
                    self.row_callback(timestamp, float(inlet), float(outlet))
                time.sleep(1)

    def start(self, filename):
        self.stop_event.clear()
        tlog = threading.Thread(target=self._logger, args=(filename,), daemon=True)
        tlog.start()
        self.threads = [tlog]
        for name, port in self.ports.items():
            tread = threading.Thread(target=self._reader, args=(name, port), daemon=True)
            tread.start()
            self.threads.append(tread)

    def stop(self):
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=2)
        self.threads.clear()


class CO2App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dual CO₂ Logger with Live Plot")
        self.geometry("800x600")
        self.resizable(False, False)

        self.logger = DualCO2Logger(PORTS)
        self.logger.row_callback = self.update_plot
        self.running = False

        # UI Controls
        ttk.Label(self, text="Log file:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.fname_var = tk.StringVar(value="dual_co2_log.csv")
        self.entry = ttk.Entry(self, textvariable=self.fname_var, width=40)
        self.entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        self.button = ttk.Button(self, text="Start", width=15, command=self._toggle)
        self.button.grid(row=0, column=2, padx=10, pady=10)

        # --- Matplotlib Figure Setup ---
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
        self.ax.set_title("Live CO₂ Concentration")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("CO₂ [ppm]")
        self.ax.grid(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=3, padx=10, pady=10)

        self.times = deque(maxlen=MAX_POINTS)
        self.inlet_vals = deque(maxlen=MAX_POINTS)
        self.outlet_vals = deque(maxlen=MAX_POINTS)

        self.inlet_line, = self.ax.plot([], [], label="CO2_inlet_ppm", color='orange')
        self.outlet_line, = self.ax.plot([], [], label="CO2_outlet_ppm", color='blue')
        self.ax.legend()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle(self):
        if not self.running:
            fname = self.fname_var.get().strip()
            if not fname:
                messagebox.showerror("Filename missing", "Please enter a filename before starting.")
                return
            self.entry.configure(state="disabled")
            self.button.configure(text="Stop")
            self.running = True
            threading.Thread(target=self.logger.start, args=(fname,), daemon=True).start()
        else:
            self.logger.stop()
            self.entry.configure(state="normal")
            self.button.configure(text="Start")
            self.running = False

    def update_plot(self, t: datetime, inlet: float, outlet: float):
        self.times.append(t)
        self.inlet_vals.append(inlet)
        self.outlet_vals.append(outlet)

        # Update data
        self.inlet_line.set_data(self.times, self.inlet_vals)
        self.outlet_line.set_data(self.times, self.outlet_vals)

        # Update x-axis
        if len(self.times) > 1:
            t0 = self.times[0]
            t1 = self.times[-1]
            window = timedelta(minutes=MAX_MINUTES)
            if (t1 - t0) < window:
                self.ax.set_xlim(t0, t0 + window)
            else:
                self.ax.set_xlim(t1 - window, t1)

            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

        # Update y-axis
        all_vals = self.inlet_vals + self.outlet_vals
        if all_vals:
            min_y = min(all_vals)
            max_y = max(all_vals)
            self.ax.set_ylim(min_y - 20, max_y + 20)

        self.canvas.draw_idle()

    def _on_close(self):
        if self.running:
            if messagebox.askyesno("Quit", "Measurement still running — stop and quit?"):
                self._toggle()
        self.destroy()


if __name__ == "__main__":
    CO2App().mainloop()
