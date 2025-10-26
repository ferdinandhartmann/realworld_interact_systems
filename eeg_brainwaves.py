# neurofeedback_clean_ratio.py
import time
import numpy as np
from bitalino import BITalino
from scipy.signal import butter, lfilter, welch
from pyqtgraph.Qt import QtCore, QtWidgets
import pyqtgraph as pg
from scipy.signal import butter, sosfiltfilt

# ===== CONFIG =====
macAddress = "98:D3:11:FE:02:74"  # Your BITalino MAC address
CHANNEL = 0  # Analog input channel
fs = 1000  # Sampling rate (Hz)
nSamples = 50  # Samples per read (~0.2s)
history_secs = 5  # seconds shown in raw plot
max_samples = fs * history_secs
update_period = 0.0000001  # seconds between power updates
window_size = fs  # 1-second analysis window
VCC = 3.0
GAIN = 41780.0
# ===================


def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    return butter(order, [low, high], btype="band")


def bandpass_filter(data, lowcut, highcut, fs):
    b, a = butter_bandpass(lowcut, highcut, fs)
    return lfilter(b, a, data)


def adc_to_microvolt(adc):
    eeg_v = ((adc / (2**16 - 1)) - 0.5) * (VCC / GAIN)
    return eeg_v * 1e6


def compute_band_power(signal, fs, band):
    f, psd = welch(signal, fs=fs, nperseg=256)
    idx = np.logical_and(f >= band[0], f <= band[1])
    return np.trapz(psd[idx], f[idx])


def bandpass_sos(low, high, fs, order=4):
    nyq = 0.5 * fs
    sos = butter(order, [low / nyq, high / nyq], btype="band", output="sos")
    return sos


def band_power_time_domain(x, low, high, fs):
    sos = bandpass_sos(low, high, fs)
    xf = sosfiltfilt(sos, x)  # zero-phase, no lag
    return float(np.mean(xf**2)), xf  # (power, filtered waveform)


# --- GUI setup ---
app = QtWidgets.QApplication([])
win = QtWidgets.QWidget()
win.setWindowTitle("Neurofeedback (EEG, Alpha, Beta, Gamma)")

layout = QtWidgets.QVBoxLayout()
win.setLayout(layout)

plot_raw = pg.PlotWidget(title="Raw Signal (5 s, µV)")
plot_alpha = pg.PlotWidget(title="Alpha (8–13 Hz)")
plot_beta = pg.PlotWidget(title="Beta (13–30 Hz)")
plot_gamma = pg.PlotWidget(title="Gamma (30–45 Hz)")
plot_power = pg.PlotWidget(title="Band Powers (µV²)")

for plt in [plot_raw, plot_alpha, plot_beta, plot_gamma, plot_power]:
    plt.showGrid(x=True, y=True)
    layout.addWidget(plt)

curve_raw = plot_raw.plot(pen="w")
curve_alpha = plot_alpha.plot(pen="b")
curve_beta = plot_beta.plot(pen="r")
curve_gamma = plot_gamma.plot(pen="y")

# Create three bars for alpha, beta, gamma
bars = pg.BarGraphItem(
    x=[0, 1, 2], height=[0, 0, 0], width=0.6, brushes=["b", "r", "y"]
)
plot_power.addItem(bars)
plot_power.getAxis("bottom").setTicks([[(0, "Alpha"), (1, "Beta"), (2, "Gamma")]])
plot_power.setYRange(0, 1)  # initial range; will auto-adjust later
plot_raw.setXRange(0, history_secs)
plot_raw.setLabel("left", "µV")
plot_raw.setLabel("bottom", "Time", "s")
plot_alpha.setLabel("bottom", "Samples")
plot_beta.setLabel("bottom", "Samples")
plot_gamma.setLabel("bottom", "Samples")

# Adjust the size of the plot window
win.resize(1800, 1200)  # Set width to 1200 and height to 800

win.show()

device = BITalino(macAddress)
device.start(fs, [CHANNEL])

buffer = np.zeros((0, 1))
last_update_time = time.time()


def update():
    global buffer, last_update_time
    try:
        # --- Read and update rolling buffer ---
        samples = device.read(nSamples)
        raw = samples[:, 5 + CHANNEL].astype(float)
        raw_uV = adc_to_microvolt(raw).reshape(-1, 1)
        buffer = np.vstack([buffer, raw_uV])
        if buffer.shape[0] > max_samples:
            buffer = buffer[-max_samples:]

        # --- Time axis for 5s rolling window ---
        t = np.arange(buffer.shape[0]) / fs
        curve_raw.setData(t, buffer[:, 0])
        plot_raw.setXRange(max(0, t[-1] - history_secs), t[-1])

        # --- Band Power Computation (every 0.25 s) ---
        if (time.time() - last_update_time > update_period) and buffer.shape[
            0
        ] >= window_size:
            window = buffer[:, 0]
            power_window = buffer[-1000:]

            alpha = bandpass_filter(window, 8, 13, fs)
            beta = bandpass_filter(window, 13, 30, fs)
            gamma = bandpass_filter(window, 30, 45, fs)

            # alpha_p = compute_band_power(alpha, fs, (8, 13))
            # beta_p = compute_band_power(beta, fs, (13, 30))
            # gamma_p = compute_band_power(gamma, fs, (30, 45))

            alpha_p, alpha = band_power_time_domain(window, 8, 13, fs)
            beta_p, beta = band_power_time_domain(window, 13, 30, fs)
            gamma_p, gamma = band_power_time_domain(window, 30, 45, fs)
            ratio = alpha_p / (beta_p + 1e-9)  # true physical ratio

            # --- Update filtered plots ---
            curve_alpha.setData(alpha)
            curve_beta.setData(beta)
            curve_gamma.setData(gamma)

            # Update bar chart with absolute powers
            power_forgetting_gain = 0.25
            power_update_gain = 1.0 - power_forgetting_gain
            powers = [alpha_p, beta_p, gamma_p]
            if not hasattr(update, "last_powers"):
                update.last_powers = np.array([0.0, 0.0, 0.0])
            update.last_powers = (
                power_forgetting_gain * update.last_powers
                + power_update_gain * np.array(powers)
            )
            bars.setOpts(height=update.last_powers.tolist())
            plot_power.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

            last_update_time = time.time()

    except Exception as e:
        print("⚠️ Error:", e)


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(int(1000 * nSamples / fs))


def close_app():
    print("Stopping BITalino...")
    device.stop()
    device.close()
    app.quit()


app.aboutToQuit.connect(close_app)
QtWidgets.QApplication.instance().exec_()
