import os
import numpy as np
import soundfile as sf


class CompressedSteganography:
    """
    Handles steganography for lossless compressed audio (OGG, FLAC).
    NOTE (future me / future you):
  - adding MP3 (or other lossy stuff) needs a totally different approach.
  - echo hiding / phase coding might work, but MP3 compression kept
    deleting what I hid in previous testing.
"""

SUPPORTED_EXTENSIONS = {".ogg", ".flac"}

# used when we read float samples and want to mess with bits as integers
# (16-bit-ish range is -32768..32767, so this is the usual scale)
INT_SCALE = 32767

def __init__(self, audio_path: str):
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    self.audio_path = audio_path
    self.extension = os.path.splitext(audio_path)[1].lower()

    # not strictly necessary, but it's an easy early fail if someone passes in random stuff
    if self.extension not in self.SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported extension '{self.extension}'. "
            f"Supported: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
        )

# ------------------------------------------------------------------
# LSB Encoding
# ------------------------------------------------------------------

def hide(self, secret_path: str, output_path: str):
    payload = self._build_payload(secret_path)
    bits_to_hide = self._bytes_to_bits(payload)

    samples, sample_rate = self._load_audio()
    flat = samples.flatten()

    # convert float samples -> int so we can do LSB operations
    int_samples = self._to_int_array(flat)

    if len(bits_to_hide) > len(int_samples):
        raise ValueError(
            "Secret file is too large for this audio.\n"
            f"  Need {len(bits_to_hide)} samples\n"
            f"  Have {len(int_samples)} samples"
        )

    stego_int = self._embed_bits(int_samples, bits_to_hide)

    # back to floats for saving
    stego_float = self._to_float_array(stego_int)
    stego_samples = stego_float.reshape(samples.shape)

    self._save_audio(stego_samples, sample_rate, output_path)

    print(f"-- '{secret_path}' successfully hidden in '{output_path}'")
    self._print_capacity_info(len(bits_to_hide), len(int_samples))

#LSB Decoding
def extract(self, output_dir: str = "."):
    samples, _ = self._load_audio()
    flat = samples.flatten()
    int_samples = self._to_int_array(flat)

    # payload format:
    #   [2B filename_len][filename bytes][8B file_size][file bytes]
    filename_len = self._read_int_from_lsbs(int_samples, start_bit=0, num_bytes=2)

    name_bytes = self._read_bytes_from_lsbs(
        int_samples, start_bit=16, num_bytes=filename_len
    )
    filename = name_bytes.decode("utf-8")  # if this breaks, payload is probably corrupt

    size_start_bit = 16 + filename_len * 8
    file_size = self._read_int_from_lsbs(
        int_samples, start_bit=size_start_bit, num_bytes=8
    )

    data_start_bit = size_start_bit + 64  # 8 bytes * 8 bits
    secret_data = self._read_bytes_from_lsbs(
        int_samples, start_bit=data_start_bit, num_bytes=file_size
    )

    # I kept forgetting to create the directory in earlier runs
    os.makedirs(output_dir, exist_ok=True)

    out_path = os.path.join(output_dir, filename)
    with open(out_path, "wb") as f:
        f.write(secret_data)

    print(f"-- Extracted '{filename}' ({file_size} bytes) -> '{out_path}'")

########################## Payload construction ############################

def _build_payload(self, secret_path: str) -> bytes:
    with open(secret_path, "rb") as f:
        file_data = f.read()

    filename = os.path.basename(secret_path).encode("utf-8")
    filename_len = len(filename).to_bytes(2, "big")
    file_size = len(file_data).to_bytes(8, "big")

    return filename_len + filename + file_size + file_data

######################### LSB core ############################

# hiding bits in audio file
@staticmethod
def _embed_bits(samples: np.ndarray, bits: list[int]) -> np.ndarray:
    modified = samples.copy()

    # this could be vectorized, but the loop is way easier to debug
    for i, bit in enumerate(bits):
        modified[i] = (int(modified[i]) & ~1) | (1 if bit else 0)

    return modified

@staticmethod
def _read_bytes_from_lsbs(samples: np.ndarray, start_bit: int, num_bytes: int) -> bytes:
    result = []

    # nested loops are ugly but kind of readable here
    for i in range(num_bytes):
        byte = 0
        base = start_bit + i * 8
        for j in range(8):
            byte = (byte << 1) | (int(samples[base + j]) & 1)
        result.append(byte)

    return bytes(result)

@classmethod
def _read_int_from_lsbs(cls, samples: np.ndarray, start_bit: int, num_bytes: int) -> int:
    raw = cls._read_bytes_from_lsbs(samples, start_bit, num_bytes)
    return int.from_bytes(raw, "big")

########################## Audio I/O helpers ############################

def _load_audio(self) -> tuple[np.ndarray, int]:
    # soundfile gives floats nicely; we scale back to ints for LSB work
    samples, sample_rate = sf.read(self.audio_path, dtype="float32")
    return samples, sample_rate

def _save_audio(self, samples: np.ndarray, sample_rate: int, output_path: str):
    fmt = self.extension.lstrip(".")  # "flac"/"ogg"
    sf.write(output_path, samples, sample_rate, format=fmt)

def _to_int_array(self, samples: np.ndarray) -> np.ndarray:
    # NOTE: int32 to avoid any overflow weirdness while we mask bits
    return (samples * self.INT_SCALE).astype(np.int32)

def _to_float_array(self, samples: np.ndarray) -> np.ndarray:
    return samples.astype(np.float32) / self.INT_SCALE

######################### Bit manipulation helpers ############################

@staticmethod
def _bytes_to_bits(data: bytes) -> list[int]:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

@staticmethod
def _print_capacity_info(bits_used: int, total_samples: int):
    pct = (100 * bits_used / total_samples) if total_samples else 0.0
    print(f"    Samples used: {bits_used} / {total_samples} ({pct:.2f}%)")