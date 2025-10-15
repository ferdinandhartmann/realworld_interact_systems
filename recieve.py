from pylsl import StreamInlet, resolve_byprop
import numpy as np
import time
from collections import deque

print("# Looking for an available OpenSignals stream...")
streams = resolve_byprop("name", "OpenSignals")
inlet = StreamInlet(streams[0])

buffer = []

import matplotlib.pyplot as plt
# Get information about the stream
stream_info = inlet.info()

# Get individual attributes
stream_name = stream_info.name()
stream_mac = stream_info.type()
stream_host = stream_info.hostname()
stream_n_channels = stream_info.channel_count()

# Print stream metadata
print(f"Stream Name: {stream_name}")
print(f"Stream MAC Address (Type): {stream_mac}")
print(f"Stream Host: {stream_host}")
print(f"Number of Channels: {stream_n_channels}")

# Store sensor channel info & units in the dictionary
stream_channels = dict()
channels = stream_info.desc().child("channels").child("channel")

# Loop through all available channels
for i in range(stream_n_channels):
    # Get the channel number (e.g. 1)
    channel = i + 1
    # Get the channel type (e.g. ECG)
    sensor = channels.child_value("sensor")
    # Get the channel unit (e.g. mV)
    unit = channels.child_value("unit")
    # Store the information in the stream_channels dictionary
    stream_channels.update({channel: [sensor, unit]})
    channels = channels.next_sibling()

# Print channel information
print("Stream Channels:")
for channel, info in stream_channels.items():
    print(f"Channel {channel}: Sensor={info[0]}, Unit={info[1]}")

# Plotting data for all 6 channels
if 6 > stream_n_channels:
    print("The stream does not have 6 channels.")
else:
    print("Plotting data for all 6 channels...")
    plt.ion()  # Turn on interactive mode
    fig, axs = plt.subplots(6, 1, figsize=(10, 15), sharex=True)
    x_data = [deque(maxlen=100) for _ in range(6)]  # Store the last 100 samples for x-axis
    y_data = [deque(maxlen=100) for _ in range(6)]  # Store the last 100 samples for y-axis
    lines = []

    for i in range(6):
        lines.append(axs[i].plot([], [], label=f"Channel {i + 1}")[0])
        axs[i].set_title(f"Channel {i + 1} - {stream_channels[i + 1][0]}")
        axs[i].set_ylabel(f"Value ({stream_channels[i + 1][1]})")
        axs[i].legend()

    axs[-1].set_xlabel("Time (s)")

    start_time = time.time()
    while True:
        sample, timestamp = inlet.pull_sample()
        current_time = time.time() - start_time

        for i in range(6):
            x_data[i].append(current_time)
            y_data[i].append(sample[i])
            lines[i].set_xdata(x_data[i])
            lines[i].set_ydata(y_data[i])
            axs[i].relim()
            axs[i].autoscale_view()

        plt.pause(0.01)
