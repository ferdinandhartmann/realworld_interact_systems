from typing import Tuple
import numpy as np
from bitalino import BITalino
from scipy.signal import butter, lfilter
import time
import threading, time
from collections import deque


# ====== CONFIG ======
EEG_MAC = "98:D3:11:FE:02:74"
EEG_CHANNEL = 0
EEG_FS = 1000
EEG_VCC = 3.0
EEG_GAIN = 41780.0
THRESHOLD_UV_LOW = 35
N_SAMPLES = 50
EEG_PLOT_LENGTH = 3 * EEG_FS
# =====================


# ====== Base classes ======
class InputSource:
    def read(self) -> float:
        """Return (flex, ext) in [0,1]. Override in subclasses."""
        return 0.0


class KeyboardInput(InputSource):
    """Keyboard input mapped to pseudo-EMG (using pygame)."""

    def __init__(self, pygame):
        self.pg = pygame

    def read(self) -> float:
        keys = self.pg.key.get_pressed()
        ratio = 1.0 if (keys[self.pg.K_SPACE] or keys[self.pg.K_UP]) else (0.5 if keys[self.pg.K_DOWN] else 0.0)
        return ratio


class EMGInput(InputSource):
    """Non-blocking EMG input using a background thread that outputs ratio."""

    def __init__(
        self, mac="98:D3:11:FE:02:74", fs=1000, channels=(1, 3), n_samples=100
    ):
        self.dev = BITalino(mac)
        self.dev.start(fs, list(channels))
        self.fs = fs
        self.channels = channels
        self.n_samples = n_samples
        self.ratio = 1.0
        self._running = True
        self.ext = 0.0
        self.boost_ext = 1  # Factor to boost extensor stddev when above threshold
        self.boost_ext_threshold = 1.00  # Threshold for extensor stddev to apply boost

        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()
        print(f"✅ Async EMGInput running on channels {channels} @ {fs} Hz")

    def _reader(self):
        while self._running:
            try:
                samples = self.dev.read(self.n_samples)
                raw = samples[:, 5:].astype(float)
                flex = raw[:, 0]
                ext = raw[:, 1]

                flex_mv = (flex / (2**16 - 1)) * 3.3
                ext_mv = (ext / (2**16 - 1)) * 3.3

                flex_std = np.std(flex_mv)
                self.ext = np.std(ext_mv)
                # print(f"🔍 flex_std: {flex_std:.4f} mV, ext_std: {self.ext:.4f} mV")

                # Increase ext_std further if it is significantly large
                if self.ext > self.boost_ext_threshold:
                    self.ext *= self.boost_ext  # Scale factor can be adjusted
                    # print(f"🔧 Boosted ext_std to {self.ext:.4f} mV")

                self.ratio = (flex_std + 1e-6) / (self.ext + 1e-6)

            except Exception as e:
                print("⚠️ EMG read error:", e)
                time.sleep(0.05)

    def read(self) -> float:
        return self.ratio

    def get_ext_std(self) -> float:
        return self.ext

    def close(self):
        self._running = False
        try:
            self.dev.stop()
            self.dev.close()
            print("🧠 BITalino device closed.")
        except Exception as e:
            print("⚠️ Error closing BITalino:", e)


class SmoothedInput(InputSource):
    """Applies exponential smoothing & deadzone to ratio-based input."""

    def __init__(
        self,
        source: InputSource,
        alpha: float = 0.92,
        deadzone: float = 0.05,
        offset: float = 0.0
    ):
        self.src = source
        self.alpha = float(alpha)
        self.dead = float(deadzone)
        self.ratio = 0.0
        self.offset = float(offset)


    def read(self) -> float:
        ratio = self.src.read()

        # ratio = np.clip(ratio, 0.0, 4.0)
        # # normalize from 0 to 3 to 0 to 1
        # ratio = ratio / 4.0
        ratio -= self.offset

        # # apply deadzone
        # if ratio < self.dead:
        #     ratio = 0.0

        # exponential smoothing
        self.ratio = self.alpha * ratio + (1 - self.alpha) * self.ratio

        # Debug (can disable for performance)
        # print(f"SmoothedInput: raw={ratio:.3f}, smoothed={self.ratio:.3f}")
        return self.ratio


# ====== EEG Blink Detector ======
class EEGBlinkInput(InputSource):
    """
    Reads EEG signal from BITalino and detects blinks.
    Output: (blink_detected, 0.0)
    """

    def __init__(self, mac=EEG_MAC, channel=EEG_CHANNEL, threshold_uv=THRESHOLD_UV_LOW):
        self.dev = BITalino(mac)
        self.dev.start(EEG_FS, [channel])
        self.channel = channel
        self.buffer = np.zeros(0)
        self.live_plot_buffer = np.zeros(0)  # For visualization
        self.buffer_lock = threading.Lock()
        self.threshold = threshold_uv  # µV threshold, same as reaction.py
        self.last_blink_time = 0.0
        self.min_blink_interval = 0.09  # seconds to ignore double detections
        self.blink_detected = 0.0
        self._running = True
        self.downsample_blink_detection = 0
        self.total_samples = 0

        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()
        print(f"✅ Async EEGInput running on channels {self.channel} @ {EEG_FS} Hz")

    # --- conversion helpers ---
    def adc_to_microvolt(self, adc):
        eeg_v = ((adc / (2**16 - 1)) - 0.5) * (EEG_VCC / EEG_GAIN)
        return eeg_v * 1e6

    def bandpass_filter(self, data, lowcut=1.0, highcut=15.0, order=2):
        b, a = butter(
            order, [lowcut / (EEG_FS / 2), highcut / (EEG_FS / 2)], btype="band"
        )
        return lfilter(b, a, data)

    # --- main read ---
    def _reader(self) -> float:
        while self._running:
            try:
                samples = self.dev.read(N_SAMPLES)
                raw = samples[:, 5 + self.channel].astype(float)
                microvolt = self.adc_to_microvolt(raw)
                microvolt = abs(microvolt)
                num_new = len(microvolt)
                self.total_samples += num_new
                with self.buffer_lock:
                    self.live_plot_buffer = np.concatenate([self.live_plot_buffer, microvolt])
                    size = self.live_plot_buffer.size
                    # print(f"Live plot buffer size: {size}")
                    if self.live_plot_buffer.size > EEG_PLOT_LENGTH:
                        self.live_plot_buffer = self.live_plot_buffer[-EEG_PLOT_LENGTH:]

                # preprocess
                # filt = self.bandpass_filter(microvolt)
                max_amplitude = np.min(microvolt)
                # print(f"🔍 EEG max_amplitude: {max_amplitude:.1f} µV")
                # print(f"🔍 EEG max_amplitude: {max_amplitude:.1f} µV")
                # --- blink detection logic ---
                self.blink_detected = 0.0
                self.downsample_blink_detection += 1
                if self.downsample_blink_detection > 0:
                    if np.min(microvolt) < THRESHOLD_UV_LOW:
                        print(f"⚡ Blink detected, min uv: {np.min(microvolt)}")
                        self.downsample_blink_detection = 0
                        self.blink_detected = 1.0

                # now = time.time()
                # if (
                #     max_amplitude < self.threshold
                #     and (now - self.last_blink_time) > self.min_blink_interval
                # ):
                # self.last_blink_time = now

            except Exception as e:
                print(f"⚠️ Error reading BITalino: {e}")
                return 0.0

    def read(self) -> float:
        return self.blink_detected

    # --- clean shutdown ---
    def close(self):
        self._running = False
        try:
            self.dev.stop()
            self.dev.close()
            print("🧠 BITalino EEG device closed.")
        except Exception as e:
            print(f"⚠️ Error closing BITalino: {e}")
