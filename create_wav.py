import wave
import array
import sys
import os

def create_silent_wav_py(filename: str, duration_ms: int = 500, sample_rate: int = 16000, channels: int = 1, sampwidth: int = 2):
    nframes = int((duration_ms / 1000.0) * sample_rate)
    comptype = "NONE"
    compname = "not compressed"
    data = array.array('h', [0] * nframes * channels) # 'h' is for signed short (16-bit)
    
    dir_path = os.path.dirname(filename)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.setnframes(nframes)
        wf.setcomptype(comptype, compname)
        wf.writeframes(data.tobytes())
    print(f"Created silent WAV: {filename}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for filename in sys.argv[1:]:
            create_silent_wav_py(filename, 500)
