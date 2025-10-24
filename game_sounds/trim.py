from pydub import AudioSegment

# === Config ===
input_path = "game_sounds/levelup.mp3"
output_path = "game_sounds/levelup_trimmed.mp3"
cut_seconds = 2

# === Load & trim ===
sound = AudioSegment.from_file(input_path)
trimmed = sound[: -int(cut_seconds * 1000)]  # cut from the end
trimmed.export(output_path, format="mp3")

print(f"✅ Trimmed file saved to {output_path}")
