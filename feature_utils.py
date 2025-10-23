import numpy as np
from scipy.signal import welch
from scipy.stats import entropy
import biosignalsnotebooks as bsnb
from sklearn.preprocessing import StandardScaler


def spectral(sig, fs=1000):
    f, Pxx = welch(sig, fs=fs)
    if np.sum(Pxx) == 0:
        return 0.0, 0.0
    Pxx /= np.sum(Pxx)
    return np.sum(f * Pxx), entropy(Pxx)


def extract_emg_features(segment, fs=1000):
    """Extract 17 EMG features (8 per channel + ratio)."""
    ch_flex = bsnb.raw_to_phy("EMG", "biosignalsplux", segment[:, 0], 16, "mV")
    ch_ext = bsnb.raw_to_phy("EMG", "biosignalsplux", segment[:, 1], 16, "mV")

    def feats(x):
        sc, se = spectral(x, fs)
        return [
            np.std(x),
            np.max(x),
            np.sum(np.diff(np.sign(x)) != 0) / len(x),
            np.std(np.abs(x)),
            np.sum(np.abs(np.diff(x))),
            np.sum(np.abs(np.diff(x)) > 0.02),
            sc,
            se,
        ]

    f1, f2 = feats(ch_flex), feats(ch_ext)
    ratio = (np.std(ch_flex) + 1e-6) / (np.std(ch_ext) + 1e-6)
    features = np.concatenate([f1, f2, [ratio]])

    return features


def extract_emg_ratio(segment, fs=1000):
    """Extract 17MG ratio."""
    ch_flex = bsnb.raw_to_phy("EMG", "biosignalsplux", segment[:, 0], 16, "mV")
    ch_ext = bsnb.raw_to_phy("EMG", "biosignalsplux", segment[:, 1], 16, "mV")

    ratio = (np.std(ch_flex) + 1e-6) / (np.std(ch_ext) + 1e-6)
    
    return ratio
