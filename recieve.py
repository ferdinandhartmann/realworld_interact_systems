from pylsl import StreamInlet, resolve_stream
import numpy as np
import time

print("# Looking for an available OpenSignals stream...")
streams = resolve_stream("name", "OpenSignals")
inlet = StreamInlet(streams[0])

buffer = []

while True:
    sample, timestamp = inlet.pull_sample()
    buffer.append(sample)

    # Process every 100 samples (for example)
    if len(buffer) >= 100:
        data = np.array(buffer)
        buffer.clear()

        # TODO: pass `data` to your extract_features() and classifier
        print(f"Received {data.shape} samples, ready for feature extraction")
