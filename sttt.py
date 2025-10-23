from game_input import EEGBlinkInput, THRESHOLD_UV_LOW
import time 
if __name__ == "__main__":
    eeg = EEGBlinkInput()
    try:
        while True:
            blink, _ = eeg.read()
            if blink:
                print("Blink detected!")
            time.sleep(0.05)
    except KeyboardInterrupt:
        eeg.close()
