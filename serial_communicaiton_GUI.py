import serial
import threading
import time
import csv
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
import os

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

PORTS = {
    "CO2_inlet_ppm":  "COM5",
    "CO2_outlet_ppm": "COM6",
}
BAUDRATE = 19200
TIMEOUT = 1

MAX_MINUTES = 30

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
        self.row_callback = None

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
        self.title("Dual CO₂ Logger with Live Data & Full Plot")
        self.geometry("1000x750")
        self.resizable(False, False)

        self.logger = DualCO2Logger(PORTS)
        self.logger.row_callback = self.update_plot
        self.running = False

        # UI Controls
        ttk.Label(self, text="Log file:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.fname_var = tk.StringVar(value= "CO2_log_" + datetime.now().strftime("%Y-%m-%d_%H-%M") + "_")#"dual_co2_log.csv") # 
        #self.fname_var = tk.StringVar(value="dual_co2_log.csv")
        self.entry = ttk.Entry(self, textvariable=self.fname_var, width=50)
        self.entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        self.button = ttk.Button(self, text="Start", width=15, command=self._toggle)
        self.button.grid(row=0, column=2, padx=10, pady=10)

        # Matplotlib: two subplots
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=False)
        self.fig.subplots_adjust(hspace=0.4)
        self.ax1.set_title("Live CO₂ (last 30 min)")
        self.ax2.set_title("Full CO₂ Measurement")
        for ax in (self.ax1, self.ax2):
            ax.set_ylabel("CO₂ [ppm]")
            ax.grid(True)

        self.ax2.set_xlabel("Time")
        self.ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=3, padx=10, pady=10)

        # Data containers
        self.all_times = []
        self.all_inlet = []
        self.all_outlet = []

        # Plot line handles
        self.live_inlet,  = self.ax1.plot([], [], label="CO2_inlet_ppm", color='orange')
        self.live_outlet, = self.ax1.plot([], [], label="CO2_outlet_ppm", color='blue')
        self.full_inlet,  = self.ax2.plot([], [], label="CO2_inlet_ppm", color='orange')
        self.full_outlet, = self.ax2.plot([], [], label="CO2_outlet_ppm", color='blue')

        self.ax1.legend()
        self.ax2.legend()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle(self):
        if not self.running:
            fname = self.fname_var.get().strip()
            if not fname:
                messagebox.showerror("Filename missing", "Please enter a filename before starting.")
                return
            if not fname.endswith(".csv"):
                fname += ".csv"
            fname = "log_files/" + fname  # Ensure log_files directory exists
            os.makedirs(os.path.dirname(fname), exist_ok=True)  # Create directory if it doesn't
            # check if file already exists
            if os.path.exists(fname):
                if not messagebox.askyesno("File exists", f"{fname} already exists. Overwrite?"):
                    return
            self.entry.configure(state="disabled")
            self.button.configure(text="Stop")
            self.running = True
            self.all_times.clear()
            self.all_inlet.clear()
            self.all_outlet.clear()
            threading.Thread(target=self.logger.start, args=(fname,), daemon=True).start()
        else:
            self.logger.stop()
            self.entry.configure(state="normal")
            self.button.configure(text="Start")
            self.running = False
            self.fname_var = tk.StringVar(value= "CO2_log_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_")#"dual_co2_log.csv") # 
            self.entry = ttk.Entry(self, textvariable=self.fname_var, width=50)
            self.entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")

    def update_plot(self, t: datetime, inlet: float, outlet: float):
        self.all_times.append(t)
        self.all_inlet.append(inlet)
        self.all_outlet.append(outlet)

        # --- Top plot: last 30 minutes ---
        window = timedelta(minutes=MAX_MINUTES)
        t_now = self.all_times[-1]
        t_min = t_now - window

        # Filter last 30 min for live plot
        live_indices = [i for i, ti in enumerate(self.all_times) if ti >= t_min]
        live_times = [self.all_times[i] for i in live_indices]
        live_inlet = [self.all_inlet[i] for i in live_indices]
        live_outlet = [self.all_outlet[i] for i in live_indices]

        self.live_inlet.set_data(live_times, live_inlet)
        self.live_outlet.set_data(live_times, live_outlet)

        if live_times:
            self.ax1.set_xlim(live_times[0], live_times[-1])
            min_y = min(live_inlet + live_outlet)
            max_y = max(live_inlet + live_outlet)
            self.ax1.set_ylim(min_y - 20, max_y + 20)

        # --- Bottom plot: full history ---
        self.full_inlet.set_data(self.all_times, self.all_inlet)
        self.full_outlet.set_data(self.all_times, self.all_outlet)

        if self.all_times:
            self.ax2.set_xlim(self.all_times[0], self.all_times[-1])
            min_y = min(self.all_inlet + self.all_outlet)
            max_y = max(self.all_inlet + self.all_outlet)
            self.ax2.set_ylim(min_y - 20, max_y + 20)

        self.canvas.draw_idle()

    def _on_close(self):
        if self.running:
            if messagebox.askyesno("Quit", "Measurement still running — stop and quit?"):
                self._toggle()
        self.destroy()
        # end script
        self.logger.stop()
        print("Application closed. All threads stopped.")

        # end mainloop
        self.quit()


if __name__ == "__main__":
    CO2App().mainloop()
