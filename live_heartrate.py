import time
import numpy as np
from collections import deque
from bitalino import BITalino
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
import biosignalsnotebooks as bsnb
from scipy.signal import welch
from scipy.signal import butter, filtfilt, welch, find_peaks

# --------------------------
# CONFIG
# --------------------------
macAddress = "98:D3:11:FE:02:74"
acqChannels = [1]  # ECG channel actually 2
samplingRate = 100
nSamples = 10
window_size = 500  # 1 s window for spectral analysis
avg_window_secs = 10  # show 30 s average HR

# --------------------------
# BITalino connection
# --------------------------
print(f"Connecting to BITalino device {macAddress} ...")
device = BITalino(macAddress)
device.start(samplingRate, acqChannels)
print("Connected and acquisition started")

# --------------------------
# GUI setup
# --------------------------
app = QtWidgets.QApplication([])
pg.setConfigOptions(antialias=True)
win = pg.GraphicsLayoutWidget(show=True, title="ECG Heart Rate Monitor")
win.resize(1500, 1000)

# --- Heart Rate label (left) ---
hr_label = pg.LabelItem(justify="center", color="w")
win.addItem(hr_label, row=0, col=0)

# --- ECG Plot (right) ---
plot = win.addPlot(row=0, col=1, title="ECG Signal (Channel 4)")
plot.showGrid(x=True, y=True)
plot.setLabel("bottom", "Time (s)")
plot.setLabel("left", "Amplitude (mV)")  # display in mV for clarity
curve = plot.plot(pen=pg.mkPen(color=(0, 255, 200), width=2))
plot.getAxis("left").setWidth(80)


# --- Heart Rate Trend Plot (below ECG) ---
hr_plot = win.addPlot(row=1, col=1, title="Heart Rate Trend (Last 60s)")
hr_plot.showGrid(x=True, y=True)
hr_plot.setLabel("bottom", "Time (s)")
hr_plot.setLabel("left", "BPM")
hr_curve = hr_plot.plot(pen=pg.mkPen(color=(255, 100, 100), width=2))
hr_plot.getAxis("left").setWidth(80)

# Buffer for 60 seconds of heart rate
hr_trend_data = deque(maxlen=60)
hr_trend_time = deque(maxlen=60)
trend_counter = 0


# --------------------------
# Buffers
# --------------------------
max_samples = samplingRate * avg_window_secs
data = deque(maxlen=max_samples)
x_axis = deque(maxlen=max_samples)
sample_counter = 0
last_update_time = time.time()
hr_history = deque(maxlen=avg_window_secs)


def bandpass_filter(signal, fs, lowcut=0.5, highcut=40.0, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype="band")
    return filtfilt(b, a, signal)


def compute_heart_rate(signal, fs):
    # Convert raw → volts and then to mV
    signal_V = bsnb.raw_to_phy(
        "ECG", "biosignalsplux", signal, resolution=16, option="V"
    )
    signal_mV = signal_V * 1000

    # --- Band-pass filter (0.5–40 Hz) ---
    filtered = bandpass_filter(signal_mV, fs)

    # # --- Auto-flip if inverted ---
    # if np.mean(filtered) < 0:
    #     filtered = -filtered

    # --- Normalize amplitude if too small (<0.2 mV) ---
    if np.std(filtered) < 0.2:
        filtered = filtered * (0.2 / (np.std(filtered) + 1e-12))

    # --- Adaptive threshold ---
    thr = np.percentile(filtered, 95) * 0.6
    thr = max(thr, 0.1)
    # --- Smooth signal slightly to suppress T-waves ---
    smoothness = 5  # Smoothing window size (1 disables smoothing)
    filtered_smooth = np.convolve(filtered, np.ones(smoothness)/smoothness, mode='same')

    # --- Require at least 0.6 s between R-peaks (≈100 BPM max) ---
    min_distance = int(fs * 0.6)
    peaks, _ = find_peaks(filtered_smooth, distance=min_distance, height=thr)
    #  Alternative simpler peak detection without smoothing:

    # peaks, _ = find_peaks(filtered, distance=fs * 0.25, height=thr)

    bpm = 0.0
    if len(peaks) > 1:
        rr_intervals = np.diff(peaks) / fs
        bpm = 60.0 / np.mean(rr_intervals)

    return bpm, filtered


# --------------------------
# Live update loop
# --------------------------
def update():
    global sample_counter, last_update_time, trend_counter
    try:
        samples = device.read(nSamples)
        analog = samples[:, 5:].astype(float)
        ecg_raw = -analog[:, 0]

        for val in ecg_raw:
            data.append(val)
            x_axis.append(sample_counter / samplingRate)
            sample_counter += 1

        # Convert and plot ECG
        _, ecg_mV = compute_heart_rate(np.array(data), samplingRate)
        curve.setData(list(x_axis), ecg_mV)
        plot.setXRange(max(0, x_axis[-1] - avg_window_secs), x_axis[-1])

        # Update HR label every second
        if time.time() - last_update_time > 1.0 and len(data) >= window_size:
            window = np.array(list(data)[-window_size:])
            bpm, _ = compute_heart_rate(window, samplingRate)
            hr_history.append(bpm)
            avg_hr = np.mean(hr_history)

            hr_label.setText(
                f"<div style='text-align:center; color:#00FFFF;'>"
                f"<h1 style='font-size:70px;'>{avg_hr:.0f} BPM</h1>"
                f"<h3>avg over 30s</h3></div>"
            )
            print(f"Instant: {bpm:.1f} BPM | 30s avg: {avg_hr:.1f} BPM")

            # --- Update HR trend plot ---
            hr_trend_data.append(avg_hr)
            hr_trend_time.append(trend_counter)

                # # --- Smooth the HR trend for nicer visuals ---
                # if len(hr_trend_data) > 3:
                #     smoothed_hr = np.convolve(list(hr_trend_data), np.ones(3) / 3, mode="same")
                # else:
                #     smoothed_hr = list(hr_trend_data)

            smoothed_hr = hr_trend_data

            hr_curve.setData(list(hr_trend_time), smoothed_hr)
            hr_plot.setXRange(max(0, trend_counter - 60), trend_counter)
            trend_counter += 1

            last_update_time = time.time()

    except Exception as e:
        print(f"Error: {e}")


# --------------------------
# Timer
# --------------------------
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(10)

# --------------------------
# Run
# --------------------------
try:
    QtWidgets.QApplication.instance().exec()
except KeyboardInterrupt:
    print("Interrupted.")
finally:
    device.stop()
    device.close()
    print("BITalino connection closed.")
