import time
import sys
import numpy as np
import joblib
from collections import deque
from bitalino import BITalino
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from scipy.stats import linregress
import biosignalsnotebooks as bsnb
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel
from scipy.stats import entropy
from scipy.signal import welch

# --------------------------
# CONFIG
# --------------------------
macAddress = "98:D3:11:FE:02:74"
# acqChannels = [0, 1, 2, 3, 4, 5]
acqChannels = [1, 2, 3, 4]
acqChannels_plot = [2, 3, 4]
samplingRate = 1000
nSamples = 100
window_size = 2500  # 1 second window for feature extraction

# Load your trained model
model = joblib.load("model/knn_classifier.pkl")
print("Loaded KNN model")
acception_labels = np.load("model/acception_labels.npy")
print("Loaded feature mask:", acception_labels)

# --------------------------
# BITalino connection
# --------------------------
print(f"Connecting to BITalino device {macAddress} ...")
device = BITalino(macAddress)
device.start(samplingRate, acqChannels)
print("Connected and acquisition started")

# --------------------------
# Setup GUI
# --------------------------
app = QtWidgets.QApplication([])
pg.setConfigOptions(antialias=True)

win = pg.GraphicsLayoutWidget(show=True, title="BITalino Real-Time Classification")
win.resize(1400, 1000)

# --------------------------
# Create the channel plots
# --------------------------
plots, curves = [], []
for i, ch in enumerate(acqChannels_plot):
    p = win.addPlot(row=i + 1, col=0)
    p.showGrid(x=True, y=True)
    p.setLabel("left", f"Channel {ch}")
    if i == len(acqChannels_plot) - 1:
        p.setLabel("bottom", "Time (s)")
    c = p.plot(pen=pg.mkPen(color=(ch * 40 % 255, 180, 255), width=1))
    p.getAxis("left").setWidth(60)  # Increase axis space (default is ~30)
    plots.append(p)
    curves.append(c)

# --- Create label for class text ---
label = pg.LabelItem(justify="center", color="w")
win.addItem(label, row=0, col=0, colspan=2)

# --- Create and add the gesture image widget ---
img_label = QLabel()
pixmap = QPixmap("icons/image_none.png")
img_label.setPixmap(pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio))

# Wrap QLabel in a proxy so PyQtGraph can place it in the layout
proxy = QtWidgets.QGraphicsProxyWidget()
proxy.setWidget(img_label)

# Add the image to the right-hand column
win.addItem(proxy, row=1, col=1, rowspan=len(acqChannels_plot))


history_secs = 10
max_samples = samplingRate * history_secs
data = [deque(maxlen=max_samples) for _ in acqChannels]
x_axis = deque(maxlen=max_samples)
sample_counter = 0


# --------------------------
# Feature extraction function
# -------------------------

def spectral(signal):
    f, Pxx = welch(signal, fs=1000)
    if np.sum(Pxx) == 0 or np.isnan(np.sum(Pxx)):
        return 0.0, 0.0
    else:
        Pxx_norm = Pxx / (np.sum(Pxx) + 1e-12)
        spectral_centroid = np.sum(f * Pxx_norm)
        spectral_entropy = entropy(Pxx_norm)
        return spectral_centroid, spectral_entropy

def extract_features(signal):
    emg_flexor_channel = 1
    emg_adductor_channel = 3
    acc_channel = 2

    signal = np.array(signal)
    emg_flexor = signal[:, emg_flexor_channel]
    emg_adductor = signal[:, emg_adductor_channel]
    acc_z = signal[:, acc_channel]

    emg_flexor_conv = bsnb.raw_to_phy(
        "EMG",
        device="biosignalsplux",
        raw_signal=emg_flexor,
        resolution=16,
        option="mV",
    )
    emg_adductor_conv = bsnb.raw_to_phy(
        "EMG",
        device="biosignalsplux",
        raw_signal=emg_adductor,
        resolution=16,
        option="mV",
    )
    acc_z_conv = bsnb.raw_to_phy(
        "ACC", device="biosignalsplux", raw_signal=acc_z, resolution=16, option="g"
    )
    
    spectral_centroid_flex, spectral_entropy_flex = spectral(emg_flexor_conv)
    features_emg_flexor = [
        np.std(emg_flexor_conv),
        np.max(emg_flexor_conv),
        np.sum(np.diff(np.sign(emg_flexor_conv)) != 0) / len(emg_flexor_conv),
        np.std(np.abs(emg_flexor_conv)),
        np.sum(np.abs(np.diff(emg_flexor_conv))),
        np.sum(np.abs(np.diff(emg_flexor_conv)) > 0.02),
        spectral_centroid_flex,
        spectral_entropy_flex,
    ]

    spectral_centroid_add, spectral_entropy_add = spectral(emg_adductor_conv)
    features_emg_adductor = [
        np.std(emg_adductor_conv),
        np.max(emg_adductor_conv),
        np.sum(np.diff(np.sign(emg_adductor_conv)) != 0) / len(emg_adductor_conv),
        np.std(np.abs(emg_adductor_conv)),
        np.sum(np.abs(np.diff(emg_adductor_conv))),
        np.sum(np.abs(np.diff(emg_adductor_conv)) > 0.02),
        spectral_centroid_add,
        spectral_entropy_add,
    ]

    m_acc_z = np.mean(acc_z_conv)
    sigma_acc_z = np.std(acc_z_conv)
    max_acc_z = np.max(acc_z_conv)
    zcr_acc_z = np.sum(np.diff(np.sign(acc_z_conv)) != 0) / len(acc_z_conv)
    slope_acc_z = linregress(np.arange(len(acc_z_conv)), acc_z_conv)[0]

    features_acc = [m_acc_z, sigma_acc_z, max_acc_z, zcr_acc_z, slope_acc_z]
    features_13 = np.concatenate(
        [features_emg_flexor, features_emg_adductor, features_acc]
    )

    max_per_feature = np.load("model/max_per_feature.npy")
    normalized_features_13 = features_13 / (max_per_feature + 1e-12)
    return normalized_features_13


# --------------------------
# Live update
# --------------------------
buffer = np.empty((0, len(acqChannels)))
last_prediction = None
last_update_time = time.time()


def update():
    global buffer, last_prediction, last_update_time
    try:
        samples = device.read(nSamples)
        analog = samples[:, 5:].astype(float)
        buffer = np.vstack([buffer, analog])
        if buffer.shape[0] > max_samples:
            buffer = buffer[-max_samples:]

        t_values = np.arange(buffer.shape[0]) / samplingRate
        x_axis.clear()
        x_axis.extend(t_values)

        for j in range(len(acqChannels_plot)):
            data[j].clear()
            data[j].extend(buffer[:, j])
            curves[j].setData(t_values, buffer[:, j])
            plots[j].setXRange(max(0, t_values[-1] - history_secs), t_values[-1])

        # Every 1 second, classify
        if time.time() - last_update_time > 0.5 and buffer.shape[0] >= window_size:
            window = buffer[-window_size:]
            feats = extract_features(window)
            reduced = feats[acception_labels]
            pred = model.predict([reduced])[0]
            last_prediction = pred
            label.setText(f"<h2>Predicted Class: <b>{pred}</b></h2>")
            last_update_time = time.time()

            if pred == 0:
                img_path = "icons/image_none.png"
            elif pred == 1:
                img_path = "icons/image_paper.png"
            elif pred == 2:
                img_path = "icons/image_scissors.png"
            elif pred == 3:
                img_path = "icons/image_rock.png"

            pixmap = QPixmap(img_path)
            img_label.setPixmap(pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio))
            print(f"Predicted Class: {pred}")

    except Exception as e:
        print(f"Error: {e}")


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
