import time, random
import numpy as np
from bitalino import BITalino
from pyqtgraph.Qt import QtCore, QtWidgets
import pyqtgraph as pg
from PyQt5.QtGui import QPainter, QBrush, QColor, QPen

# ===== CONFIG =====
MAC_ADDRESS = "98:D3:11:FE:02:74"
CHANNEL = 0
SAMPLING_RATE = 1000
N_SAMPLES = 50
THRESHOLD_UV_LOW = 35.3
VCC = 3.0
GAIN = 41780.0
Y_RANGE_MAX = 36.5  # µV
Y_RANGE_MIN = 34.5  # µV
CUE_DELAY_RANGE = (4, 8)
MAX_VISIBLE_TIME = 8.0  # seconds of EEG data visible
WAIT_AFTER_MISS = 2.0  # extra seconds before next trial if missed
WAIT_FOR_BLINK = 1  # seconds to wait after blink detection
REACT_PLOT_Y_RANGE = WAIT_FOR_BLINK*1000  # ms
# ===================
cue_lines = []

def adc_to_microvolt(adc):
    eeg_v = ((adc / (2**16 - 1)) - 0.5) * (VCC / GAIN)
    return eeg_v * 1e6


class CueCircle(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor("red")
        self.setMinimumSize(250, 250)
        self.setStyleSheet("background-color: white;")

    def setColor(self, color_name):
        self.color = QColor(color_name)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor("white"))

        # Draw circle
        rect = self.rect()
        d = min(rect.width(), rect.height()) - 20
        circle_rect = QtCore.QRectF(
            rect.center().x() - d / 2, rect.center().y() - d / 2, d, d
        )
        painter.setBrush(QBrush(self.color))
        painter.setPen(QPen(QtCore.Qt.black, 4))
        painter.drawEllipse(circle_rect)


# --- GUI setup ---
app = QtWidgets.QApplication([])
win = QtWidgets.QWidget()
win.setWindowTitle("🧠 Blink Reaction Test (Visible Cue, Fixed Paint)")
win.resize(1800, 1000)  

main_layout = QtWidgets.QVBoxLayout(win)

# --- Top: EEG plot and cue ---
top_layout = QtWidgets.QHBoxLayout()
main_layout.addLayout(top_layout)

# EEG Plot
plot = pg.PlotWidget(title="Raw Signal (µV)")
plot.showGrid(x=True, y=True)
plot.setYRange(Y_RANGE_MIN, Y_RANGE_MAX)
curve = plot.plot(pen="w")
top_layout.addWidget(plot, 3)

# Cue circle widget
cue_widget = CueCircle()
top_layout.addWidget(cue_widget, 1)

# --- Bottom: Reaction time bars ---
react_plot = pg.PlotWidget(title="Reaction Times (ms)")
react_plot.showGrid(x=True, y=True)
react_plot.setLabel("bottom", "Trial #")
react_plot.setLabel("left", "Reaction Time (ms)")
bars = pg.BarGraphItem(x=[], height=[], width=0.6, brush="g")
react_plot.addItem(bars)
react_plot.setYRange(0, REACT_PLOT_Y_RANGE)
main_layout.addWidget(react_plot)

win.show()

# --- BITalino setup ---
device = BITalino(MAC_ADDRESS)
device.start(SAMPLING_RATE, [CHANNEL])

buffer = np.zeros(0)
cue_shown = False
reaction_recorded = False
cue_time = None
end_time = None
trial_start = time.time()
next_delay = random.uniform(*CUE_DELAY_RANGE)
trial_count = 0
reaction_times = []
vline = None
counter_random_blink = 0


def start_new_trial(longer_wait=False):
    """Reset for next trial."""
    global cue_shown, reaction_recorded, cue_time, end_time, trial_start, next_delay

    cue_shown = False
    reaction_recorded = False
    cue_time = None
    end_time = None
    cue_widget.setColor("red")
    trial_start = time.time()
    extra = WAIT_AFTER_MISS if longer_wait else 0.0
    next_delay = random.uniform(*CUE_DELAY_RANGE) + extra
    print(f"\n🔁 New trial starting in {next_delay:.1f}s...")


def update():
    global buffer, cue_shown, reaction_recorded, cue_time, end_time
    global trial_count, reaction_times, cue_lines, counter_random_blink

    samples = device.read(N_SAMPLES)
    raw = samples[:, 5 + CHANNEL].astype(float)
    microvolt = adc_to_microvolt(raw)
    microvolt = abs(microvolt)
    buffer = np.concatenate([buffer, microvolt])
    if buffer.size > SAMPLING_RATE * MAX_VISIBLE_TIME:
        buffer = buffer[-int(SAMPLING_RATE * MAX_VISIBLE_TIME) :]

    # Update EEG plot
    t = np.arange(buffer.size) / SAMPLING_RATE
    curve.setData(t, buffer)
    plot.setXRange(max(0, t[-1] - MAX_VISIBLE_TIME), t[-1])

    counter_random_blink += 1
    # print(microvolt)
    if counter_random_blink > 0:
        if np.max(microvolt) < THRESHOLD_UV_LOW:
            print(f"⚡ Blink detected, max uv: {np.max(microvolt)}")
            counter_random_blink = 0

    # --- Move cue lines with time window ---
    if cue_lines:
        # Only keep those that are still visible
        new_lines = []
        for line, cue_t in cue_lines:
            # Calculate relative x position
            x_rel = t[-1] - (time.time() - cue_t)
            line.setPos(x_rel)
            if x_rel >= t[-1] - MAX_VISIBLE_TIME:  # still visible
                new_lines.append((line, cue_t))
            else:
                plot.removeItem(line)  # line left the plot
        cue_lines = new_lines

    # --- Show cue ---
    if not cue_shown and time.time() - trial_start > next_delay:
        cue_widget.setColor("green")
        cue_shown = True
        cue_time = time.time()
        end_time = cue_time + WAIT_FOR_BLINK
        print("🟢 Cue shown — blink now!")

        x_cue = t[-1]
        vline = pg.InfiniteLine(pos=x_cue, angle=90, pen=pg.mkPen("g", width=2))
        plot.addItem(vline)
        cue_lines.append((vline, cue_time))

    # --- Detect blink ---
    if cue_shown and not reaction_recorded:
        if np.max(microvolt) < THRESHOLD_UV_LOW:
            rt = (time.time() - cue_time) * 1000
            print(f"⚡ Blink detected after {rt:.1f} ms")
            reaction_recorded = True
            trial_count += 1
            reaction_times.append(rt)
            x_vals = np.arange(1, len(reaction_times) + 1)
            bars.setOpts(x=x_vals, height=reaction_times, width=0.6, brush='b')

            # Auto-scale reaction plot
            react_plot.enableAutoRange(axis="y", enable=True)

            # QtCore.QTimer.singleShot(int(WAIT_AFTER_MISS * 1000), start_new_trial)

    # --- End of trial ---
    if cue_shown and end_time and time.time() > end_time:
        if not reaction_recorded:
            print("❌ No blink detected — missed trial.")
            cue_widget.setColor("gray")
            trial_count += 1
            reaction_times.append(0)

            # Draw individual red bar for missed trial
            miss_bar = pg.BarGraphItem(x=[trial_count], height=[0], width=0.6, brush="r")
            react_plot.addItem(miss_bar)

            # keep previous green bars
            x_vals = np.arange(1, len(reaction_times))
            bars.setOpts(x=x_vals, height=reaction_times[:-1], width=0.6, brush="b")

            # wait longer but keep plotting
            # QtCore.QTimer.singleShot(int(WAIT_AFTER_MISS * 1000), start_new_trial)
            start_new_trial(longer_wait=False)

        else:
            start_new_trial(longer_wait=False)


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(int(1000 * N_SAMPLES / SAMPLING_RATE))


def close_app():
    print("Stopping BITalino...")
    device.stop()
    device.close()
    app.quit()


app.aboutToQuit.connect(close_app)
QtWidgets.QApplication.instance().exec_()
