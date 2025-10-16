import time
import sys
import numpy as np
from collections import deque

from bitalino import BITalino
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore



# --------------------------
# 1. Connect to BITalino
# --------------------------
# Replace with your actual MAC address
macAddress = "98:D3:11:FE:02:74"

# Settings
batteryThreshold = 30
acqChannels = [0, 1, 2, 3, 4, 5]
samplingRate = 1000  # Hz
nSamples = 100

print(f"Connecting to BITalino device {macAddress} ...")
device = BITalino(macAddress)
device.battery(batteryThreshold)

print("Connected.")
print(f"Firmware Version: {device.version()}")

# Start acquisition
device.start(samplingRate, acqChannels)
print(f"Started acquisition at {samplingRate} Hz on channels {acqChannels}")

# --------------------------
# 2. Setup PyQtGraph window
# --------------------------
app = QtWidgets.QApplication([])
pg.setConfigOptions(antialias=True)
win = pg.GraphicsLayoutWidget(show=True, title="BITalino Live Stream (10s Window)")
win.resize(1000, 800)
win.setWindowTitle("Real-Time BITalino Viewer")

plots, curves = [], []
history_secs = 10
max_samples = samplingRate * history_secs

data = [deque(maxlen=max_samples) for _ in acqChannels]
x_axis = deque(maxlen=max_samples)
sample_counter = 0

for i, ch in enumerate(acqChannels):
    p = win.addPlot(row=i, col=0)
    p.showGrid(x=True, y=True)
    p.setLabel("left", f"Channel {ch}")
    if i == len(acqChannels) - 1:
        p.setLabel("bottom", "Time (s)")
    p.getAxis("left").enableAutoSIPrefix(False)
    p.getAxis("bottom").enableAutoSIPrefix(False)
    c = p.plot(pen=pg.mkPen(color=(ch * 40 % 255, 180, 255), width=1))
    plots.append(p)
    curves.append(c)

# --------------------------
# 3. Live Update Function
# --------------------------
start_time = time.time()


def update():
    global sample_counter
    try:
        samples = device.read(nSamples)
        analog = samples[:, 5:].astype(float)  # columns A1–A6

        # Compute time values for this batch
        t_values = np.arange(sample_counter, sample_counter + nSamples) / samplingRate
        sample_counter += nSamples

        # Append time values (extend instead of append)
        x_axis.extend(t_values)

        # Update each channel plot
        for j, ch in enumerate(acqChannels):
            data[j].extend(analog[:, ch])
            # Ensure matching lengths
            min_len = min(len(x_axis), len(data[j]))
            curves[j].setData(list(x_axis)[-min_len:], list(data[j])[-min_len:])
            plots[j].setXRange(max(0, t_values[-1] - history_secs), t_values[-1])

    except Exception as e:
        print(f"Error: {e}")


# QTimer for smooth updates
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(10)  # ms → update ~100 Hz (draw loop, not sampling)

# --------------------------
# 4. Run the event loop
# --------------------------
try:
    QtWidgets.QApplication.instance().exec()
except KeyboardInterrupt:
    print("Interrupted by user.")
finally:
    device.stop()
    device.close()
    print("BITalino connection closed.")
