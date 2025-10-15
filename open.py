import biosignalsnotebooks as bsnb

recording = bsnb.load(
    "/home/ferdinand/Documents/OpenSignals (r)evolution/temp/opensignals_98D311FE0274_2025-10-15_20-02-54.h5"
)

print(recording.keys())
