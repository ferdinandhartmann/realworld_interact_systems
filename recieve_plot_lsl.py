from pylsl import StreamInlet, resolve_byprop
import numpy as np
from collections import deque
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
import sys
import time

# ------------------------------------------------------
# 1. Connect to OpenSignals LSL Stream
# ------------------------------------------------------
print("# Looking for an available OpenSignals stream...")
streams = resolve_byprop("name", "OpenSignals")
if not streams:
    print("No OpenSignals stream found.")
    sys.exit()

inlet = StreamInlet(streams[0])
info = inlet.info()

stream_name = info.name()
stream_type = info.type()
stream_host = info.hostname()
stream_n_channels = info.channel_count()  # Exclude sequence channel

print(f"Stream Name: {stream_name}")
print(f"Stream Type: {stream_type}")
print(f"Stream Host: {stream_host}")
print(f"Number of Channels: {stream_n_channels}")
print("Channel Names:")
for i in range(stream_n_channels):
    ch = info.desc().child("channels").child("channel")
    for _ in range(i):
        ch = ch.next_sibling()
    channel_name = ch.child_value("label")
    print(f"Channel {i+1}: {channel_name}")

# ------------------------------------------------------
# 2. Read channel metadata
# ------------------------------------------------------
channels_meta = {}
ch = info.desc().child("channels").child("channel")
for i in range(stream_n_channels):
    sensor = ch.child_value("sensor")
    unit = ch.child_value("unit")
    channels_meta[i] = (sensor if sensor else f"CH{i+1}", unit if unit else "raw")
    ch = ch.next_sibling()

# Skip first channel (nSeq)
usable_channels = list(range(1, stream_n_channels))
print("Active channels:")
for i in usable_channels:
    print(f"  {i}: {channels_meta[i][0]} ({channels_meta[i][1]})")


# ------------------------------------------------------
# 3. Setup PyQtGraph window
# ------------------------------------------------------
app = QtWidgets.QApplication([])
pg.setConfigOptions(antialias=True)
win = pg.GraphicsLayoutWidget(show=True, title="OpenSignals Live Stream (10 s window)")
win.resize(1000, 800)
win.setWindowTitle("Real-Time OpenSignals Viewer")

plots, curves = [], []
history_secs = 1000
sample_rate = 1
max_samples = history_secs * sample_rate

data = [deque(maxlen=max_samples) for _ in usable_channels]
x_axis = deque(maxlen=max_samples)
sample_counter = 0

for plot_idx, ch_idx in enumerate(usable_channels):
    p = win.addPlot(row=plot_idx, col=0)
    p.showGrid(x=True, y=True)
    p.setLabel("left", f"{channels_meta[ch_idx][0]} ({channels_meta[ch_idx][1]})")
    if plot_idx == len(usable_channels) - 1:
        p.setLabel("bottom", "Time (s)")
    # disable scientific notation
    p.getAxis("left").setStyle(
        autoExpandTextSpace=True, tickFont=pg.Qt.QtGui.QFont("Arial", 8)
    )
    p.getAxis("left").enableAutoSIPrefix(False)
    p.getAxis("bottom").enableAutoSIPrefix(False)
    c = p.plot(pen=pg.mkPen(color=(ch_idx * 40 % 255, 180, 255), width=1))
    plots.append(p)
    curves.append(c)

    # # 3.1. Print channel data every second
    # def print_channel_data():
    #     for idx, ch_idx in enumerate(usable_channels):
    #         print(f"{channels_meta[ch_idx][0]}: {list(data[idx])[-3:]}")
    #     print(" ")

    # print_timer = QtCore.QTimer()
    # print_timer.timeout.connect(print_channel_data)
    # print_timer.start(1000)  # 1000 ms = 1 second

# ------------------------------------------------------
# 4. Live update function
# ------------------------------------------------------
def update():
    global sample_counter
    sample, timestamp = inlet.pull_sample(timeout=0.0)
    if sample is not None:

        sample_counter += 1
        x_axis.append(timestamp*1000)

        # Convert voltage back to 10-bit ADC range (0-1023) #####################
        # adc_values = [s * 1023 / 3.3 for s in sample]
        adc_values = sample  # Use raw values directly

        for idx, ch_idx in enumerate(usable_channels):
            data[idx].append(adc_values[ch_idx - 1])
            curves[idx].setData(list(x_axis), list(data[idx]))
            plots[idx].setXRange(max(0, timestamp - history_secs), timestamp)


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(1)  # 1 ms update → supports 1000 Hz

# ------------------------------------------------------
# 5. Start the Qt event loop
# ------------------------------------------------------
if (sys.flags.interactive != 1) or not hasattr(QtCore, "PYQT_VERSION"):
    QtWidgets.QApplication.instance().exec()
