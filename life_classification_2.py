import time
import numpy as np
import joblib
from collections import deque
from bitalino import BITalino
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from scipy.signal import welch
from scipy.stats import entropy
import biosignalsnotebooks as bsnb
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel
from sklearn.preprocessing import StandardScaler

from feature_utils import extract_emg_features

# --------------------------
# CONFIGURATION
# --------------------------
macAddress = "98:D3:11:FE:02:74"
acqChannels_real = [2, 4]  #CH2 = flexor, CH4 = extensor
acqChannels = [ch - 1 for ch in acqChannels_real]
fs = 1000
nSamples = 50
window_size = int(0.5 * fs)  # 0.5 s window
update_period = 0.25  # classify every 0.25 s

# Load trained model and normalization
model = joblib.load("model_2/nn_classifier.pkl")
# max_per_feature = np.load("model_2/max_per_feature.npy")
scaler = joblib.load("model_2/feature_scaler.pkl")
gesture_names = ["relax", "rock", "paper", "scissors"]
print("✅ Loaded MLP model")

# --------------------------
# BITalino connection
# --------------------------
print(f"Connecting to BITalino device {macAddress} ...")
device = BITalino(macAddress)
device.start(fs, acqChannels)
print("Connected and acquisition started")

# --------------------------
# Setup GUI
# --------------------------
app = QtWidgets.QApplication([])
pg.setConfigOptions(antialias=True)
win = pg.GraphicsLayoutWidget(show=True, title="BITalino Real-Time EMG Classification")
win.resize(1600, 1200)
win.ci.layout.setColumnStretchFactor(0, 3)  # EMG plots (left column) → 3x wider
win.ci.layout.setColumnStretchFactor(1, 1)  # Image column → narrower

# Label for predicted class
label = pg.LabelItem(justify="center", color="w")
# --------------------------
# GUI LAYOUT
# --------------------------

# Create EMG plots on the left column
plots, curves = [], []
for i, ch in enumerate(acqChannels):
    p = win.addPlot(row=i, col=0)
    p.showGrid(x=True, y=True)
    p.setLabel("left", f"CH{ch+1}")
    if i == len(acqChannels) - 1:
        p.setLabel("bottom", "Time (s)")
    c = p.plot(pen=pg.mkPen(color=(ch * 40 % 255, 180, 255), width=1))
    plots.append(p)
    curves.append(c)

# --------------------------
# Gesture image (right column)
# --------------------------
img_label = QLabel()
img_label.setAlignment(QtCore.Qt.AlignCenter)  # 👈 center the image
img_label.setStyleSheet("background-color: black;")  
pixmap = QPixmap("icons/image_none.png")
img_label.setPixmap(pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio))
proxy_img = QtWidgets.QGraphicsProxyWidget()
proxy_img.setWidget(img_label)

# Add image in right column, spanning all EMG plot rows
win.addItem(proxy_img, row=0, col=1, rowspan=len(acqChannels))

# --------------------------
# Label placed *on top* of image
# --------------------------
label = pg.LabelItem(justify="center", color="w")
# Put the label above the image, same column (col=1), right above proxy_img
win.addItem(label, row=0, col=1)

# --------------------------
# Feature bar chart (bottom, full width)
# --------------------------
feature_plot = win.addPlot(row=len(acqChannels) + 1, col=0, colspan=2)
feature_plot.setLabel("left", "Normaized Feature Values")
feature_plot.setLabel("bottom", "Feature")
feature_plot.setYRange(-3, 3)

feature_names = [
    "F_std",
    "F_max",
    "F_zcr",
    "F_stdAbs",
    "F_wl",
    "F_wamp",
    "F_sc",
    "F_se",
    "E_std",
    "E_max",
    "E_zcr",
    "E_stdAbs",
    "E_wl",
    "E_wamp",
    "E_sc",
    "E_se",
    "ratio",
]
feature_bar = pg.BarGraphItem(
    x=np.arange(len(feature_names)),
    height=np.zeros(len(feature_names)),
    width=0.6,
    brush="orange",
)
feature_plot.addItem(feature_bar)
feature_plot.getAxis("bottom").setTicks([list(enumerate(feature_names))])


# --------------------------
# Buffers
# --------------------------
history_secs = 5
max_samples = fs * history_secs
data = [deque(maxlen=max_samples) for _ in acqChannels]
buffer = np.empty((0, len(acqChannels)))
last_update_time = time.time()
last_predictions = deque(maxlen=5)  # for smoothing


# --------------------------
# Live update function
# --------------------------
def update():
    global buffer, last_update_time
    try:
        samples = device.read(nSamples)
        analog = samples[:, 5:].astype(float)
        buffer = np.vstack([buffer, analog])
        if buffer.shape[0] > max_samples:
            buffer = buffer[-max_samples:]

        t = np.arange(buffer.shape[0]) / fs
        for j, ch in enumerate(acqChannels):
            data[j].clear()
            data[j].extend(buffer[:, j])
            curves[j].setData(t, buffer[:, j])
            plots[j].setXRange(max(0, t[-1] - history_secs), t[-1])

        # Classify every 0.25 s
        if (
            time.time() - last_update_time > update_period
            and buffer.shape[0] >= window_size
        ):
            window = buffer[-window_size:, :]
            feats = extract_emg_features(window, fs=fs)
            feats = scaler.transform([feats])[0]

            feature_bar.setOpts(height=feats)

            flex_std = np.std(window[:, 0])
            ext_std = np.std(window[:, 1])

            pred = model.predict([feats])[0]

            # Smooth prediction using majority of last 5
            last_predictions.append(pred)
            smoothed_pred = max(set(last_predictions), key=last_predictions.count)
            gesture = gesture_names[smoothed_pred]
            label.setText(f"<h2>Predicted: <b>{gesture}</b></h2>")
            print("Pred:", gesture)
            last_update_time = time.time()

            img_path = (
                f"icons/image_{gesture.lower()}.png"
                if gesture != "relax"
                else "icons/image_none.png"
            )
            pixmap = QPixmap(img_path)
            img_label.setPixmap(pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio))

    except Exception as e:
        print("Error:", e)


# --------------------------
# Timer for GUI updates
# --------------------------
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(10)

# --------------------------
# Run app
# --------------------------
try:
    app.exec()
except KeyboardInterrupt:
    print("Interrupted by user.")
finally:
    device.stop()
    device.close()
    print("BITalino connection closed.")
