## Real-World Interaction Systems with BITalino


### Rock, Paper, Scissors Detection:
Updated Rock, Paper, Scissors estimation with MLP:
- Use **rock_paper_scissor_2.py** to train the model with the `min_data`. (Data was collected with CH2 on flexor on underarm and CH4 on extension on underarm)
- Use **live_classification_2.py** for live classification.
- The script **feature_utils.py** is utilized to extract the necessary features.


https://github.com/user-attachments/assets/75693e20-819d-44a5-919e-fed72749256f



### Live ECG Heart Rate Moitoring
<img width="800" height="1032" alt="image" src="https://github.com/user-attachments/assets/a5180275-dcb0-4175-a417-26fc99783f4f" />


## Games

### EEG Signal Brain Waves (Alpha, Betta, Gamma and Power Ratio)
Connect EEG to port A0. Place the two main nodes on your forehead 2cm apart and the neutral one (white) on the bone behind the ear.
<img width="800" height="1548" alt="Screenshot from 2025-10-26 18-51-02" src="https://github.com/user-attachments/assets/9ec158c0-adda-406d-a046-273faf3d56b8" />


### Flappy Bird Game With EEG Signal (Blink Detection)
<img width="800" alt="Screenshot from 2025-10-26 18-52-28" src="https://github.com/user-attachments/assets/ce5e9bb6-9a25-4d85-a63b-d0dbaf229934" />


### Running Jump Game with EMG Hand flexing/streching Ratio detection

...

### Old Rock Paper Scissors Detection with KNN
This project utilizes **rock_paper_scissor.ipynb** to detect hand movements for the game Rock, Paper, Scissors. It leverages data from **2 EMG sensors** and **1 accelerometer**.

### Detected Movements:
- **0**: No movement
- **1**: Paper
- **2**: Rock
- **3**: Scissors

For live classification then run **live_classification.py**
