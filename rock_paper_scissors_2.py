import os, glob
import numpy as np
import biosignalsnotebooks as bsnb
from scipy.signal import welch
from scipy.stats import entropy
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
from copy import deepcopy
from sklearn.preprocessing import StandardScaler

from feature_utils import extract_emg_features

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
data_folder = "min_data"
fs = 1000
gesture_names = ["relax", "rock", "paper", "scissors"]
list_examples = glob.glob(f"{data_folder}/*.h5")

signal_dict = {}
for example in list_examples:
    base = os.path.basename(example)
    example_class = base.split("_")[-1].split(".")[0]
    example_trial = "1"

    if example_class not in signal_dict:
        signal_dict[example_class] = {}

    data = bsnb.load(example)
    signal_dict[example_class][example_trial] = {
        "CH2": data["CH2"],  # finger flexor
        "CH4": data["CH4"],  # finger extensor
    }

print("Loaded:", signal_dict.keys())

# ---------------------------------------------------
# FEATURE EXTRACTION WITH WINDOWING (no accelerometer)
# ---------------------------------------------------
from scipy.signal import welch
from scipy.stats import entropy
import numpy as np
from copy import deepcopy

window_size = int(0.5 * fs)  # 0.5 s → 500 samples
step = int(0.25 * fs)  # 50% overlap


def spectral(sig):
    f, Pxx = welch(sig, fs=fs)
    if np.sum(Pxx) == 0:
        return 0, 0
    Pxx /= np.sum(Pxx)
    return np.sum(f * Pxx), entropy(Pxx)


features_dict = deepcopy(signal_dict)

for class_i in signal_dict.keys():
    for trial in signal_dict[class_i].keys():
        features_dict[class_i][trial] = []  # list of feature vectors

        ch_flex = signal_dict[class_i][trial]["CH2"]
        ch_ext = signal_dict[class_i][trial]["CH4"]

        # Slide over signal in 0.5s windows
        for start in range(0, len(ch_flex) - window_size, step):
            seg_flex = ch_flex[start : start + window_size]
            seg_ext = ch_ext[start : start + window_size]
            
            features = extract_emg_features(np.column_stack([seg_flex, seg_ext]), fs=fs)
            
            features_dict[class_i][trial].append(features)

print("Feature extraction complete (windowed).")

# ---------------------------------------------------
# BUILD DATASET ARRAYS (flatten windowed features)
# ---------------------------------------------------
X, y = [], []
for g_idx, g in enumerate(gesture_names):
    if g not in features_dict:
        continue
    for trial in features_dict[g]:
        # Each trial is a list of window feature vectors
        for feats in features_dict[g][trial]:
            X.append(feats)
            y.append(g_idx)

X, y = np.array(X), np.array(y)
print("Dataset shape:", X.shape)

# ---------------------------------------------------
# NORMALIZE, TRAIN & EVALUATE
# ---------------------------------------------------
# max_per_feature = np.max(X, axis=0)
# Xn = X / (max_per_feature + 1e-12)
scaler = StandardScaler()
Xn = scaler.fit_transform(X)
joblib.dump(scaler, "model_2/feature_scaler.pkl")

# now you have many samples per gesture → stratify works
Xtr, Xte, ytr, yte = train_test_split(Xn, y, test_size=0.2, random_state=42, stratify=y)

mlp = MLPClassifier(
    hidden_layer_sizes=(64, 32),
    activation="relu",
    solver="adam",
    max_iter=500,
    random_state=1,
)
mlp.fit(Xtr, ytr)

print("\nEvaluation report:")
print(classification_report(yte, mlp.predict(Xte), target_names=gesture_names))

# ---------------------------------------------------
# SAVE MODEL
# ---------------------------------------------------
os.makedirs("model_2", exist_ok=True)
joblib.dump(mlp, "model_2/nn_classifier.pkl")
# np.save("model_2/max_per_feature.npy", max_per_feature)
print("✅ Model saved to model_2/nn_classifier.pkl")
