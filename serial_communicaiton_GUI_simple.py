import serial
import threading
import time
import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

#--------------------------------------------------
#  Low-level acquisition & logging
#--------------------------------------------------
PORTS = {
    "CO2_inlet_ppm":  "COM3",
    "CO2_outlet_ppm": "COM4",
}
BAUDRATE = 19200
TIMEOUT   = 1    # seconds


class DualCO2Logger:
    """
    Manages two Vaisala GMP343 sensors concurrently and
    streams their latest readings to a CSV file in real time.
    """
    def __init__(self, ports: dict[str, str],
                 baudrate: int = BAUDRATE, timeout: int = TIMEOUT):
        self.ports      = ports
        self.baudrate   = baudrate
        self.timeout    = timeout
        self.stop_event = threading.Event()
        self.data_lock  = threading.Lock()
        self.data       = {name: None for name in ports}
        self.serials    = {}          # name → serial.Serial
        self.threads    = []          # reader + logger threads

    # ----- sensor helpers --------------------------------------------------
    @staticmethod
    def _activate_sensor(ser: serial.Serial) -> None:
        """Mimic holding CAPS-LOCK+Z for ≈3 s."""
        for _ in range(30):
            ser.write(b"Z")
            time.sleep(0.1)

    def _reader(self, name: str, port: str) -> None:
        """Background thread: pull lines from one sensor."""
        try:
            ser = serial.Serial(port, self.baudrate, timeout=self.timeout)
            self.serials[name] = ser
        except serial.SerialException as exc:
            print(f"[{name}] cannot open {port}: {exc}")
            return

        time.sleep(2)                       # settle
        self._activate_sensor(ser)
        time.sleep(1)
        ser.write(b"r\r\n")                 # start streaming

        while not self.stop_event.is_set():
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                with self.data_lock:
                    self.data[name] = line
        ser.close()

    # ----- logger ----------------------------------------------------------
    def _logger(self, filename: str) -> None:
        with open(filename, "w", newline="", buffering=1) as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", *self.ports.keys()])

            while not self.stop_event.is_set():
                with self.data_lock:
                    row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]] + \
                          [self.data[k] for k in self.ports]
                writer.writerow(row)
                f.flush()                   # immediate persistence
                time.sleep(1)

    # ----- public API ------------------------------------------------------
    def start(self, filename: str) -> None:
        """Launch reader+logger threads."""
        self.stop_event.clear()
        # Logger first, so no data ever lost
        tlog = threading.Thread(target=self._logger, args=(filename,), daemon=True)
        tlog.start()
        self.threads = [tlog]

        for name, port in self.ports.items():
            tread = threading.Thread(target=self._reader, args=(name, port),
                                      daemon=True)
            tread.start()
            self.threads.append(tread)

    def stop(self) -> None:
        """Signal all threads to finish and wait briefly."""
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=2)
        self.threads.clear()


#--------------------------------------------------
#  Tkinter UI
#--------------------------------------------------
class CO2App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dual CO₂ Logger")
        self.geometry("410x120")
        self.resizable(False, False)

        self.logger  = DualCO2Logger(PORTS)
        self.running = False                    # UI state flag

        # --- widgets -------------------------------------------------------
        ttk.Label(self, text="Log file:").grid(row=0, column=0,
                                               padx=10, pady=15, sticky="e")

        self.fname_var = tk.StringVar(value="dual_co2_log.csv")
        self.entry     = ttk.Entry(self, textvariable=self.fname_var, width=32)
        self.entry.grid(row=0, column=1, padx=5, pady=15)

        self.button = ttk.Button(self, text="Start", width=15,
                                 command=self._toggle)
        self.button.grid(row=1, column=0, columnspan=2, pady=10)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- callbacks --------------------------------------------------
    def _toggle(self) -> None:
        if not self.running:
            # ----------- START ----------
            fname = self.fname_var.get().strip()
            if not fname:
                messagebox.showerror("Filename missing",
                                     "Please enter a filename before starting.")
                return
            self.entry.configure(state="disabled")
            self.button.configure(text="Stop")
            self.running = True
            threading.Thread(target=self.logger.start,
                             args=(fname,), daemon=True).start()
        else:
            # ----------- STOP -----------
            self.logger.stop()
            self.entry.configure(state="normal")
            self.button.configure(text="Start")
            self.running = False

    def _on_close(self) -> None:
        if self.running:
            if messagebox.askyesno("Quit",
                                   "Measurement still running — stop and quit?"):
                self._toggle()
        self.destroy()


if __name__ == "__main__":
    CO2App().mainloop()
